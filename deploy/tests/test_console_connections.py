import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONSOLE = ROOT / "console-src" / "index.html"


class ConsoleConnectionsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = CONSOLE.read_text(encoding="utf-8")

    def test_boot_fetches_live_whatsapp_status(self) -> None:
        self.assertIn('jget(WAAPI+"/status")', self.source)
        self.assertIn('if(wd!==null){waData=wd;', self.source)

    def test_connections_never_hard_codes_whatsapp_as_connected(self) -> None:
        self.assertNotIn(
            '["W","WhatsApp alerts","Owner escalations","Linked device","Configured",true]',
            self.source,
        )
        self.assertIn('if(state==="connected")return{label:"Connected"', self.source)
        self.assertIn('if(state==="qr")return{label:"Needs linking"', self.source)
        self.assertIn('wa.detail,wa.label,wa.healthy', self.source)

    def test_connections_refreshes_whatsapp_state(self) -> None:
        self.assertIn('const loadWhatsApp=tab==="notif"||tab==="conns";', self.source)
        self.assertIn('renderNow&&(tab==="notif"||tab==="conns")', self.source)
        self.assertIn('loadNotifications({renderNow:tab==="notif"||tab==="conns"})', self.source)

    def test_status_failures_clear_stale_connection_state(self) -> None:
        self.assertIn('else{waData=null;waSig="";}', self.source)


if __name__ == "__main__":
    unittest.main()
