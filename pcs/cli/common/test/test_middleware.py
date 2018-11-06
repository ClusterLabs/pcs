from unittest import TestCase

from pcs.cli.common import middleware


class MiddlewareBuildTest(TestCase):
    def test_run_middleware_correctly_chained(self):
        log = []
        def command(lib, argv, modifiers):
            log.append('command: {0}, {1}, {2}'.format(lib, argv, modifiers))

        def mdw1(_next, lib, argv, modifiers):
            log.append(
                'mdw1 start: {0}, {1}, {2}'.format(lib, argv, modifiers)
            )
            _next(lib, argv, modifiers)
            log.append('mdw1 done')

        def mdw2(_next, lib, argv, modifiers):
            log.append(
                'mdw2 start: {0}, {1}, {2}'.format(lib, argv, modifiers)
            )
            _next(lib, argv, modifiers)
            log.append('mdw2 done')

        run_with_middleware = middleware.build(mdw1, mdw2)
        run_with_middleware(command, "1", "2", "3")
        self.assertEqual(log, [
            'mdw1 start: 1, 2, 3',
            'mdw2 start: 1, 2, 3',
            'command: 1, 2, 3',
            'mdw2 done',
            'mdw1 done',
        ])
