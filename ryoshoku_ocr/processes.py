# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Bounded subprocess execution with cooperative service shutdown."""
import subprocess
import time


def run_process(args, *, timeout, cwd, env=None, stop=None):
    deadline = time.monotonic() + timeout
    with subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE) as child:
        try:
            while True:
                if stop is not None and stop.is_set():
                    raise InterruptedError('Service is stopping')
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(args, timeout)
                try:
                    stdout, _ = child.communicate(timeout=min(remaining, .1))
                except subprocess.TimeoutExpired:
                    continue
                if child.returncode != 0:
                    raise subprocess.CalledProcessError(child.returncode, args, output=stdout)
                return stdout
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
