
import sys
import os
from datetime import datetime
import linecache
import traceback

class Exception:

    new_debug = True
    debug = False
    output = None
    command = None

    @classmethod
    def init(cls, debug=False, output=None, command=None):
        sys.excepthook = cls.exception_handler # set custom exception handler (uncaught exceptions)
        cls.output = output
        cls.command = command
        cls.debug = True if debug else False

    @classmethod
    def exception(cls, message: str, e: Exception, tb=None):
        custom_tb = sys.exc_info()[-1] if tb is None else tb
        original_tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        exception_message = (
            "-------------------------\n" 
            f"!-- Exception: {message}\n"
        )
        if custom_tb is not None:
            while custom_tb.tb_next: # loop to last traceback frame
                custom_tb = custom_tb.tb_next 
            tb_frame = custom_tb.tb_frame
            tb_line = custom_tb.tb_lineno
            func_name = tb_frame.f_code.co_name
            filename = tb_frame.f_code.co_filename
            codeline = linecache.getline(filename, tb_line).strip()
            exception_message += (
                f"!-- File: {filename}\n"
                f"!-- Function: {func_name}\n"
                f"!-- Line: {tb_line}\n"
                f"!-- Segment: {codeline}\n"
            )
        else:
            exception_message += "!-- Traceback is None\n"
        exception_message += (
            f"!-- Description: {e}\n"
            "-------------------------")
        print(exception_message)
        if cls.debug:
            debug_file = os.path.join(cls.output, "waybackup_error.log")
            print(f"Exception log: {debug_file}")
            print("-------------------------")
            print(f"Full traceback:\n{original_tb}")
            if cls.new_debug: # new run, overwrite file
                cls.new_debug = False
                f = open(debug_file, "w")
                f.write("-------------------------\n")
                f.write(f"Command: {cls.command}\n")
                f.write("-------------------------\n\n")
            else: # current run, append to file
                f = open(debug_file, "a")
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
            f.write(exception_message + "\n")
            f.write(original_tb + "\n")

    @staticmethod
    def exception_handler(exception_type, exception, traceback):
        if issubclass(exception_type, KeyboardInterrupt):
            sys.__excepthook__(exception_type, exception, traceback)
            return
        Exception.exception("UNCAUGHT EXCEPTION", exception, traceback) # uncaught exceptions also with custom scheme
    