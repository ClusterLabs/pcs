from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.cli.common import middleware


class MiddlewareBuildTest(TestCase):
    def test_run_middleware_correctly_chained(self):
        log = []
        def command(lib, argv, modificators):
            log.append('command: {0}, {1}, {2}'.format(lib, argv, modificators))

        def m1(next, lib, argv, modificators):
            log.append(
                'm1 start: {0}, {1}, {2}'.format(lib, argv, modificators)
            )
            next(lib, argv, modificators)
            log.append('m1 done')

        def m2(next, lib, argv, modificators):
            log.append(
                'm2 start: {0}, {1}, {2}'.format(lib, argv, modificators)
            )
            next(lib, argv, modificators)
            log.append('m2 done')

        run_with_middleware = middleware.build(m1, m2)
        run_with_middleware(command, "1", "2", "3")
        self.assertEqual(log, [
            'm1 start: 1, 2, 3',
            'm2 start: 1, 2, 3',
            'command: 1, 2, 3',
            'm2 done',
            'm1 done',
        ])

