import unittest

from race.path import Root


class TestCycle(unittest.TestCase):
    def _test(self, path: str, output: str):
        root = Root.from_path(list(iter(path)), )
        rtn = ''.join(root.norm)

        self.assertEqual(
            output,
            rtn,
        )

    def test_001(self):
        self._test('a', 'a')

    def test_002(self):
        self._test('ab', 'ab')

    def test_003(self):
        self._test('abab', 'abab')

    def test_004(self):
        self._test('abababbab', 'abab')

    def test_005(self):
        self._test('abcbcabcbca', 'abcbca')

    def test_006(self):
        self._test('abcbcabdbcagefgefg', 'abcbcabdbcagefg')

    def test_007(self):
        self._test('abacadaeafa', 'abacadaeafa')

    def test_008(self):
        self._test('abbabba', 'aba')

    def test_009(self):
        self._test('abcbabdba', 'abcbabdba')

    def test_010(self):
        # are we sure that's what's supposed to happen?
        self._test('aaaa', 'a')

    def test_011(self):
        self._test('ababacaca', 'abaca')

    def test_012(self):
        self._test('ababa', 'aba')

    def test_013(self):
        self._test('abcdefgabcdefgabcdefgab', 'abcdefgab')

    def test_014(self):
        self._test('ababacdcdc', 'abacdc')

    def test_015(self):
        self._test('abadacabadaca', 'abadacabadaca')

    def test_016(self):
        self._test('abadacabadacaba', 'abadacaba')
