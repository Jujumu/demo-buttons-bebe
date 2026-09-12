from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "docker" / "helpdesk" / "Dockerfile"
COMPOSE = ROOT / "docker-compose.yml"
DOCKERIGNORE = ROOT / ".dockerignore"


class DockerPackageTests(unittest.TestCase):
    def test_dockerfile_does_not_copy_env(self) -> None:
        self.assertTrue(DOCKERFILE.is_file())
        text = DOCKERFILE.read_text(encoding="utf-8")
        self.assertNotIn("COPY .env", text)
        self.assertNotIn("SHOPIFY_CLIENT_SECRET=", text)
        self.assertNotIn("AGENTMAIL_API_KEY=", text)
        self.assertIn("SHOPIFY_MUTATIONS_ENABLED=0", text)
        self.assertIn("GORGIAS_BRIDGE_ENABLED=0", text)
        self.assertIn("console-src/inbox", text)
        self.assertIn("console-src/helpdesk-agent", text)

    def test_dockerignore_excludes_secrets(self) -> None:
        self.assertTrue(DOCKERIGNORE.is_file())
        text = DOCKERIGNORE.read_text(encoding="utf-8")
        self.assertIn("**/.env", text)
        self.assertIn("**/.env.*", text)

    def test_compose_injects_runtime_env(self) -> None:
        self.assertTrue(COMPOSE.is_file())
        text = COMPOSE.read_text(encoding="utf-8")
        self.assertIn("env_file:", text)
        self.assertIn(".env", text)
        self.assertIn("SHOPIFY_MUTATIONS_ENABLED", text)
        self.assertNotIn("SHOPIFY_CLIENT_SECRET:", text)
        self.assertNotIn("shpat_", text)
        self.assertNotIn("yznyc1-ez.myshopify.com", text)
