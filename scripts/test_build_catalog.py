import unittest
from build_catalog import COUNTS, validate_rows, validate_repository


def rows():
    return [(s, a, f'<p>Original {s}:{a}</p>', '[1] Original note')
            for s, n in enumerate(COUNTS, 1) for a in range(1, n + 1)]


class ValidationTest(unittest.TestCase):
    def test_all_published_packages(self):
        validate_repository()

    def test_preserves_original_text_and_footnotes(self):
        data = validate_rows(rows())
        self.assertEqual(data['1']['1'], {'text': '<p>Original 1:1</p>',
                                        'footnotes': '[1] Original note'})

    def test_rejects_incomplete(self):
        with self.assertRaises(ValueError):
            validate_rows(rows()[:-1])

    def test_rejects_duplicate(self):
        values = rows()
        values[-1] = values[0]
        with self.assertRaises(ValueError):
            validate_rows(values)

    def test_rejects_placeholder(self):
        for text in ['', ' ', '<p></p>', '-', 'null', '…']:
            values = rows()
            values[0] = (1, 1, text, '')
            with self.assertRaises(ValueError):
                validate_rows(values)

    def test_rejects_out_of_range(self):
        values = rows()
        values[-1] = (115, 1, 'Original', '')
        with self.assertRaises(ValueError):
            validate_rows(values)


if __name__ == '__main__':
    unittest.main()
