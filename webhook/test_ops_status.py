"""Offline monitor freshness, redaction and authenticated route coverage."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from bb_webhook import ops_status
from bb_webhook.routers.dashboard import router
from bb_webhook.middleware.console_session import ConsoleSessionMiddleware


class OpsStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'status.json';self.now=datetime(2026,9,7,tzinfo=timezone.utc)
        mock=patch.object(ops_status,'STATUS',self.path);mock.start();self.addCleanup(mock.stop)

    def state(self,when=None):
        self.path.write_text(json.dumps({'checked_at':(when or self.now).isoformat(),
            'checks':{key:'ok' for key in ops_status.CHECKS}}))

    def test_missing_corrupt_and_stale_do_not_look_healthy(self):
        self.assertEqual(ops_status.summary(self.now)['status'],'missing')
        self.path.write_text('invalid');self.assertEqual(ops_status.summary(self.now)['status'],'unavailable')
        self.state(self.now-timedelta(seconds=181));self.assertEqual(ops_status.summary(self.now)['status'],'stale')
        self.state(self.now+timedelta(seconds=31));self.assertEqual(ops_status.summary(self.now)['status'],'unavailable')
        self.state();self.assertEqual(ops_status.summary(self.now)['status'],'ok')

    def test_unknown_keys_and_values_never_leak_raw_errors(self):
        self.path.write_text(json.dumps({'checked_at':self.now.isoformat(),'checks':{'secret':'private-token','processor_progress':'private-token'},'raw_error':'private-token'}))
        result=ops_status.summary(self.now)
        self.assertEqual(result['status'],'attention');self.assertNotIn('private-token',json.dumps(result))

    def test_route_rejects_anonymous_and_returns_only_summary_to_session(self):
        app=FastAPI();app.add_middleware(ConsoleSessionMiddleware);app.include_router(router)
        with TestClient(app) as client:
            with patch('bb_webhook.middleware.console_session.resolve_identity',new=AsyncMock(return_value=None)):
                self.assertEqual(client.get('/dashboard/api/ops').status_code,401)
            with patch('bb_webhook.middleware.console_session.resolve_identity',new=AsyncMock(return_value={'username':'synthetic-owner'})):
                response=client.get('/dashboard/api/ops')
                self.assertEqual(response.status_code,200);self.assertEqual(response.json()['status'],'missing')
                self.assertEqual(response.headers['cache-control'],'no-store')


if __name__=='__main__':unittest.main()
