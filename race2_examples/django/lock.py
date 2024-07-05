from argparse import ArgumentParser

from contextlib import ExitStack

from django.contrib.auth.models import User
from django.core.management import BaseCommand
from django.db import transaction, models

from race2.multiprocessing.remote import RemoteGenerator
from race2.multiprocessing.thread import ThreadGenerator
from race2.multiprocessing.trace import TraceYield
from race2.multiprocessing.yield_fun import yield_fun_yield
from race2.abstract import Execution, Visitor, ProcessID


class Lock(models.Model):
    user_id = models.IntegerField(unique=True)


def lock(user_id: int):
    with transaction.atomic():
        yield_fun_yield("entry")
        task_lock_obj, created = Lock.objects.get_or_create(user_id=user_id)
        if created:
            yield_fun_yield("created")
        else:
            yield_fun_yield("no create")


class Command(BaseCommand):
    def add_arguments(self, parser: ArgumentParser):
        # Positional arguments
        pass

    def handle(self, *args, **options):
        print("Starting")
        # type your command here

        with ExitStack() as es:
            thread_generator_1 = es.enter_context(
                ThreadGenerator(lock, read_timeout=1)
                # RemoteGenerator(checker)
                # ThreadGenerator(TraceYield(checker))
                # RemoteGenerator(es.enter_context(ThreadGenerator(TraceYield(checker))))
            )

            thread_generator_2 = es.enter_context(
                ThreadGenerator(lock, read_timeout=1)
                # RemoteGenerator(checker)
                # ThreadGenerator(TraceYield(checker))
                # RemoteGenerator(es.enter_context(ThreadGenerator(TraceYield(checker))))
            )

            customer_user_id = 123

            def factory() -> Execution:
                print("Factory")

                def handle_terminate():
                    Lock.objects.filter(user_id=customer_user_id).delete()

                exec = Execution(handle_terminate=handle_terminate)
                exec.add_process(ProcessID(1), thread_generator_2(customer_user_id))
                exec.add_process(ProcessID(0), thread_generator_1(customer_user_id))

                return exec

            print("Visiting")

            vis = Visitor(factory)
            vis.next()

            print(
                (len(vis.visited_edges), vis.instantiation_ctr, vis.paths_found_ctr),
            )

            from race2.util.graphviz import graphviz

            graphviz(visitor=vis, filename="/data/test.gv.png", should_view=False)

            # print(factory().run([1, 0]))
            # print(factory().run([0, 1]))
