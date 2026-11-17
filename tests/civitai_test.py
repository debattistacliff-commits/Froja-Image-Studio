import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import civitai
import backend


class CivitaiTests(unittest.TestCase):
    def test_hash_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model = root / 'model.bin'
            model.write_bytes(b'fingerprint')
            with patch.object(civitai, 'CACHE', root / 'cache.json'):
                self.assertEqual(civitai.sha256(model), hashlib.sha256(b'fingerprint').hexdigest())
                cached = json.loads((root / 'cache.json').read_text())
                with patch.object(Path, 'open', side_effect=AssertionError('read model again')):
                    with patch.object(civitai, '_read', return_value=cached):
                        self.assertEqual(civitai.sha256(model), hashlib.sha256(b'fingerprint').hexdigest())
                model.write_bytes(b'changed')
                self.assertEqual(civitai.sha256(model), hashlib.sha256(b'changed').hexdigest())

    def test_safe_images(self):
        images = [{'url': str(i), 'nsfwLevel': i, 'type': 'image'} for i in range(5)]
        images += [{'url': 'false', 'nsfw': False}, {'url': 'none', 'nsfw': 'None'}, {'url': 'bad', 'nsfw': True}, {'url': 'unknown'}, {'url': 'video', 'nsfwLevel': 1, 'type': 'video'}]
        self.assertEqual([i['url'] for i in civitai.safe_images(images)], ['0', '1', 'false', 'none'])
        self.assertEqual(civitai.safe_images([{'url': 'bad', 'nsfwLevel': 2, 'nsfw': False}]), [])

    def test_parse(self):
        data = {'id': 22, 'modelId': 11, 'name': 'v1', 'model': {'name': 'Example', 'type': 'LORA'}, 'baseModel': 'SDXL', 'trainedWords': ['hello']}
        info = civitai.parse_version(data, 'artist')
        self.assertEqual(info['creator'], 'artist')
        self.assertEqual(info['trained_words'], ['hello'])
        self.assertEqual(info['model_url'], 'https://civitai.com/models/11?modelVersionId=22')

    def test_preview_validation(self):
        self.assertEqual(civitai.preview_path('a' * 64, '0.jpg').name, '0.jpg')
        for digest, filename in [('../bad', '0.jpg'), ('a' * 64, '../0.jpg'), ('a' * 64, '4.jpg'), ('a' * 64, '0.svg')]:
            with self.assertRaises(ValueError):
                civitai.preview_path(digest, filename)

    def test_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'config.json'
            path.write_text(json.dumps({'other': 'value'}), encoding='utf-8-sig')
            civitai.write_settings(path, True, 'secret')
            self.assertFalse(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            self.assertEqual(json.loads(path.read_text())['other'], 'value')
            civitai.write_settings(path, False)
            self.assertEqual(json.loads(path.read_text())['civitai_api_key'], 'secret')

    def test_lookup_cache_and_not_found(self):
        import urllib.error
        with tempfile.TemporaryDirectory() as temp, patch.object(civitai, 'CACHE', Path(temp) / 'cache.json'):
            with patch.object(civitai, '_request', side_effect=urllib.error.HTTPError('url', 404, 'missing', {}, None)) as request:
                self.assertFalse(civitai.lookup('a' * 64)['found'])
                self.assertFalse(civitai.lookup('a' * 64)['found'])
                self.assertEqual(request.call_count, 1)

    def test_disabled_info_route(self):
        import urllib.parse
        with patch.object(backend, 'load_local_config', return_value={}), patch.object(backend, 'json_response') as response, patch.object(backend, 'scan_models') as scan:
            route = urllib.parse.urlparse('/api/civitai/info?kind=loras&relative=example')
            self.assertTrue(backend.optional_routes(object(), 'GET', route, urllib.parse.parse_qs(route.query)))
            self.assertEqual(response.call_args.args[1:], ({'error': 'Civitai link is off'}, 403))
            scan.assert_not_called()

    def test_found_lookup_cached_with_local_preview(self):
        version = {'id': 22, 'modelId': 11, 'name': 'v1', 'model': {'name': 'Example', 'type': 'LORA'}, 'images': [{'url': 'https://image.civitai.com/sample', 'nsfwLevel': 1, 'type': 'image'}]}
        with tempfile.TemporaryDirectory() as temp, patch.object(civitai, 'CACHE', Path(temp) / 'cache.json'), patch.object(civitai, 'PREVIEWS', Path(temp) / 'previews'):
            with patch.object(civitai, '_request', side_effect=[version, {'creator': {'username': 'artist'}}, (b'preview', 'png')]) as request:
                info = civitai.lookup('b' * 64)
                self.assertEqual(info['creator'], 'artist')
                self.assertEqual(info['images'], ['/api/civitai-preview/' + 'b' * 64 + '/0.png'])
                self.assertEqual(civitai.preview_path('b' * 64, '0.png').read_bytes(), b'preview')
                self.assertEqual(civitai.lookup('b' * 64), info)
                self.assertEqual(request.call_count, 3)

    def test_library(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(backend, 'WORKFLOW_LIBRARY', Path(temp) / 'library'):
            for _ in range(2):
                backend.save_library('Example', 'id', {'1': {'inputs': {'ckpt_name': 'test'}}}, {}, {'prompt': 'hello'}, None, b'zip')
            items = backend.library_items()['items']
            self.assertEqual({i['name'] for i in items}, {'Example', 'Example (2)'})
            for name in ['../bad', 'a/b', '.', 'bad\\name']:
                with self.assertRaises(ValueError):
                    backend.library_folder(name)


if __name__ == '__main__':
    unittest.main()
