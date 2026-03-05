import unittest
import os
from unittest.mock import patch
from tools.phases import select_files, FileList

class TestSelection(unittest.TestCase):
    @patch('tools.llm.generate_json')
    def test_select_files(self, mock_generate_json):
        # Configure the mock to return a FileList with a valid and an invalid file
        mock_generate_json.return_value = FileList(files=['existing.py', 'fake_file.py'])
        
        request = "test request"
        file_tree = "├── existing.py"
        history = ""
        
        # Call the function
        files = select_files(request, file_tree, history)
        
        # Assert that the LLM is called and returns the expected result
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0], 'existing.py')
        self.assertEqual(files[1], 'fake_file.py')

if __name__ == '__main__':
    unittest.main()
