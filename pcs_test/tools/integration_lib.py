from pcs_test.tools.command_env.calls import Queue, CallListBuilder
from pcs_test.tools.command_env.mock_runner import Runner as NewRunner


#TODO please remove this module when Runner  is not used. The only usage is
# in the module pcs_test.test_lib_commands_sbd currently.



class Runner:
    def __init__(self):
        self.set_runs([])

    def assert_everything_launched(self):
        if self.__call_queue.remaining:
            raise AssertionError(
                "There are remaining expected commands: \n    '{0}'".format(
                    "'\n    '".join([
                        call.command
                        for call in self.__call_queue.remaining
                    ])
                )
            )

    def set_runs(self, run_list):
        call_list_builder = CallListBuilder()
        for run in run_list:
            call_list_builder.place("", run)

        self.__call_queue = Queue(call_list_builder)
        self.run = NewRunner(self.__call_queue).run
