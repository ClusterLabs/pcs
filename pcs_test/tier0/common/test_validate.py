from unittest import TestCase

from pcs.common import validate


class IsInteger(TestCase):
    def test_no_range(self):
        self.assertTrue(validate.is_integer(1))
        self.assertTrue(validate.is_integer("1"))
        self.assertTrue(validate.is_integer(-1))
        self.assertTrue(validate.is_integer("-1"))
        self.assertTrue(validate.is_integer(+1))
        self.assertTrue(validate.is_integer("+1"))

        self.assertFalse(validate.is_integer(" 1"))
        self.assertFalse(validate.is_integer("\n-1"))
        self.assertFalse(validate.is_integer("\r+1"))
        self.assertFalse(validate.is_integer("1\n"))
        self.assertFalse(validate.is_integer("-1 "))
        self.assertFalse(validate.is_integer("+1\r"))

        self.assertFalse(validate.is_integer(""))
        self.assertFalse(validate.is_integer("1a"))
        self.assertFalse(validate.is_integer("a1"))
        self.assertFalse(validate.is_integer("aaa"))
        self.assertFalse(validate.is_integer(1.0))
        self.assertFalse(validate.is_integer("1.0"))

    def test_at_least(self):
        self.assertTrue(validate.is_integer(5, 5))
        self.assertTrue(validate.is_integer(5, 4))
        self.assertTrue(validate.is_integer("5", 5))
        self.assertTrue(validate.is_integer("5", 4))

        self.assertFalse(validate.is_integer(5, 6))
        self.assertFalse(validate.is_integer("5", 6))

    def test_at_most(self):
        self.assertTrue(validate.is_integer(5, None, 5))
        self.assertTrue(validate.is_integer(5, None, 6))
        self.assertTrue(validate.is_integer("5", None, 5))
        self.assertTrue(validate.is_integer("5", None, 6))

        self.assertFalse(validate.is_integer(5, None, 4))
        self.assertFalse(validate.is_integer("5", None, 4))

    def test_range(self):
        self.assertTrue(validate.is_integer(5, 5, 5))
        self.assertTrue(validate.is_integer(5, 4, 6))
        self.assertTrue(validate.is_integer("5", 5, 5))
        self.assertTrue(validate.is_integer("5", 4, 6))

        self.assertFalse(validate.is_integer(3, 4, 6))
        self.assertFalse(validate.is_integer(7, 4, 6))
        self.assertFalse(validate.is_integer("3", 4, 6))
        self.assertFalse(validate.is_integer("7", 4, 6))


class IsPortNumber(TestCase):
    def test_valid_port(self):
        self.assertTrue(validate.is_port_number(1))
        self.assertTrue(validate.is_port_number("1"))
        self.assertTrue(validate.is_port_number(65535))
        self.assertTrue(validate.is_port_number("65535"))
        self.assertTrue(validate.is_port_number(8192))

    def test_bad_port(self):
        self.assertFalse(validate.is_port_number(0))
        self.assertFalse(validate.is_port_number("0"))
        self.assertFalse(validate.is_port_number(65536))
        self.assertFalse(validate.is_port_number("65536"))
        self.assertFalse(validate.is_port_number(" 8192 "))
        self.assertFalse(validate.is_port_number(-128))
        self.assertFalse(validate.is_port_number("-128"))
        self.assertFalse(validate.is_port_number("abcd"))
