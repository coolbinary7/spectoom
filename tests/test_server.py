import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.env = dict(os.environ, SPECTOOM_ENV='production', SPECTOOM_DATA_DIR=cls.temp.name,
                       SPECTOOM_SEED_DEMO='0', SPECTOOM_SECURE_COOKIES='0')
        for role in ('USER', 'ADMIN'):
            cls.env.update({f'SPECTOOM_{role}_NAME': role,
                            f'SPECTOOM_{role}_EMAIL': role.lower()+'@example.invalid',
                            f'SPECTOOM_{role}_PASSWORD': secrets.token_hex(24)+'A1'})
        cls.patch = patch.dict(os.environ, cls.env)
        cls.patch.start()
        spec = importlib.util.spec_from_file_location('spectoom_server', ROOT/'server.py')
        cls.server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.server)

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()
        cls.temp.cleanup()

    def test_external_media_and_traversal(self):
        s = self.server
        path = s.UPLOAD_DIR/'fixture.txt'
        path.write_text('test')
        self.assertEqual(s.asset_disk_path('/media/uploads/fixture.txt'), path)
        rendered = s.RENDER_DIR/'fixture.mp4'
        rendered.write_bytes(b'test')
        self.assertEqual(s.asset_disk_path('/media/renders/fixture.mp4'), rendered)
        for folder in (s.UPLOAD_DIR, s.RENDER_DIR, s.CONVERSION_DIR, s.TMP_DIR, s.PREVIEW_DIR):
            self.assertTrue(folder.is_relative_to(Path(self.temp.name).resolve()))
        self.assertIsNone(s.asset_disk_path('/static/../server.py'))
        link = s.UPLOAD_DIR/'outside.txt'
        link.symlink_to(ROOT/'server.py')
        self.assertIsNone(s.asset_disk_path('/media/uploads/outside.txt'))

    def test_required_credentials(self):
        with patch.dict(os.environ, {'SPECTOOM_USER_PASSWORD': ''}):
            with self.assertRaises(RuntimeError):
                self.server.bootstrap_accounts_from_env()

    def test_password_hash(self):
        value = secrets.token_hex(24)
        hashed = self.server.password_hash(value)
        self.assertNotIn(value, hashed)
        self.assertTrue(self.server.password_verify(value, hashed))
        self.assertFalse(self.server.password_verify(value+'x', hashed))

    def test_http_startup_port_login_and_storage(self):
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = dict(self.env, PORT=str(port), PYTHONUNBUFFERED='1')
        env.pop('HOST', None)
        with tempfile.TemporaryFile(mode='w+') as log:
            process = subprocess.Popen([sys.executable, str(ROOT/'server.py')], env=env, stdout=log, stderr=log)
            try:
                url = f'http://127.0.0.1:{port}'
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(url+'/api/health', timeout=1) as response:
                            health = json.load(response)
                        break
                    except OSError:
                        if process.poll() is not None:
                            self.fail('Server stopped unexpectedly')
                        time.sleep(.1)
                else:
                    self.fail('Server startup timed out')
                self.assertTrue(health['ok'])
                self.assertTrue(health['storageWritable'])
                body = json.dumps({'email': env['SPECTOOM_USER_EMAIL'], 'password': env['SPECTOOM_USER_PASSWORD']}).encode()
                req = urllib.request.Request(url+'/api/login', data=body, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req) as response:
                    self.assertTrue(json.load(response)['ok'])
                    self.assertIn('HttpOnly', response.headers['Set-Cookie'])
                store = json.loads((Path(self.temp.name)/'store.json').read_text())
                self.assertEqual(store['projects'], [])
                self.assertEqual(len(store['users']), 2)
                self.assertNotIn(env['SPECTOOM_USER_PASSWORD'], json.dumps(store))
            finally:
                process.terminate()
                process.wait(timeout=10)
            log.seek(0)
            self.assertIn(f'http://0.0.0.0:{port}', log.read())
