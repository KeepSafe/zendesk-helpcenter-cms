from unittest.mock import MagicMock, patch
from unittest import TestCase
import tempfile
import services
import exceptions


class TestFilesystemService(TestCase):
    def setUp(self):
        self.service = services.FilesystemService()

    def test_die_on_wrong_format(self):
        with self.assertRaises(exceptions.FileFormatError):
            self.service.read('dummy', file_format='dummy')
        with self.assertRaises(exceptions.FileFormatError):
            self.service.save('dummy', {}, file_format='dummy')

    def test_return_empty_value_if_file_doesnt_exist(self):
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            self.assertEqual({}, self.service.read('dummy'))
            self.assertEqual({}, self.service.save('dummy', {}))

    def test_read_text_happy_path(self):
        with tempfile.NamedTemporaryFile(mode='w') as fp:
            expected = 'dummy data'
            fp.write(expected)
            fp.flush()

            actual = self.service.read(fp.name)

        self.assertEqual(expected, actual)

    def test_read_json_happy_path(self):
        with tempfile.NamedTemporaryFile(mode='w') as fp:
            fp.write('{"1":"test"}')
            fp.flush()

            actual = self.service.read(fp.name, file_format='json')

        self.assertEqual({'1': 'test'}, actual)

    def test_save_text_happy_path(self):
        with tempfile.NamedTemporaryFile(mode='w+') as fp:
            expected = 'dummy data'

            self.service.save(fp.name, expected)
            actual = fp.read()

        self.assertEqual(expected, actual)

    def test_save_json_happy_path(self):
        with tempfile.NamedTemporaryFile(mode='w+') as fp:
            self.service.save(fp.name, {'1': 'test'}, file_format='json')
            actual = fp.read()

        self.assertEqual('{\n    "1": "test"\n}', actual)
