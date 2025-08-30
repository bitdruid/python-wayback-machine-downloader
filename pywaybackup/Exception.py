import sys
import os
import re
import linecache
import traceback
from datetime import datetime

from importlib.metadata import version


class Exception:
    new_debug = True
    output = None
    command = None

    @classmethod
    def init(cls, debugfile=None, output=None, command=None):
        sys.excepthook = cls.exception_handler  # set custom exception handler (uncaught exceptions)
        cls.debugfile = debugfile
        cls.output = output
        cls.command = command

    @classmethod
    def exception(cls, message: str, e: Exception, tb=None):
        custom_tb = sys.exc_info()[-1] if tb is None else tb
        original_tb = cls.relativate_path("".join(traceback.format_exception(type(e), e, e.__traceback__)))
        exception_message = f"-------------------------\n!-- Exception: {message}\n"
        local_vars = {}
        if custom_tb is not None:
            while custom_tb.tb_next:  # loop to last traceback frame
                custom_tb = custom_tb.tb_next
            tb_frame = custom_tb.tb_frame
            tb_line = custom_tb.tb_lineno
            func_name = tb_frame.f_code.co_name
            filename = cls.relativate_path(tb_frame.f_code.co_filename)
            codeline = linecache.getline(filename, tb_line).strip()
            local_vars = tb_frame.f_locals
            exception_message += (
                f"!-- File: {filename}\n"
                f"!-- Function: {func_name}\n"
                f"!-- Line: {tb_line}\n"
                f"!-- Segment: {codeline}\n"
            )
        else:
            exception_message += "!-- Traceback is None\n"
        exception_message += f"!-- Description: {e}\n-------------------------"
        print(exception_message)
        if cls.debugfile:
            print(f"Exception log: {cls.debugfile}")
            if cls.new_debug:  # new run, overwrite file
                cls.new_debug = False
                f = open(cls.debugfile, "w", encoding="utf-8")
                f.write("-------------------------\n")
                f.write(f"Version: {version('pywaybackup')}\n")
                f.write("-------------------------\n")
                f.write(f"Command: {cls.command}\n")
                f.write("-------------------------\n\n")
            else:  # current run, append to file
                f = open(cls.debugfile, "a", encoding="utf-8")
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
            f.write(exception_message + "\n")
            f.write("!-- Local Variables:\n")
            for var_name, value in local_vars.items():
                if var_name in ["status_message", "headers"]:
                    continue
                value = cls.relativate_path(str(value))
                value = value[:666] + " ... " if len(value) > 666 else value
                f.write(f"    -- {var_name} = {value}\n")
            f.write("-------------------------\n")
            f.write(original_tb + "\n")
            f.close()

    @classmethod
    def relativate_path(cls, input_str: str) -> str:
        try:
            path_pattern = re.compile(r'File "([^"]+)"')
            if os.path.isfile(input_str):  # case single path
                return os.path.relpath(input_str, os.getcwd())
            input_modified = ""
            input_lines = input_str.split("\n")
            if len(input_lines) == 1:  # case single line
                return input_str
            for line in input_str.split("\n"):  # case multiple lines
                match = path_pattern.search(line)
                if match:
                    original_path = match.group(1)
                    relative_path = os.path.relpath(original_path, os.getcwd())
                    line = line.replace(original_path, relative_path)
                input_modified += line + "\n"
            return input_modified
        except ValueError:
            return input_str

    @staticmethod
    def exception_handler(exception_type, exception, traceback):
        if issubclass(exception_type, KeyboardInterrupt):
            sys.__excepthook__(exception_type, exception, traceback)
            return
        Exception.exception('UNCAUGHT EXCEPTION', exception, traceback)  # uncaught exceptions also with custom scheme
