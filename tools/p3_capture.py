"""P3 capture target: a titled Entry that dumps its exact content to a file on Return
(or after a safety timeout), then exits. The driver focuses it, xdotool-types the test
string, and sends Return. Reading entry.get() gives the byte-exact result the sink produced.
"""
import sys
import tkinter as tk

OUT = sys.argv[1]
root = tk.Tk()
root.title("talkhere-p3")               # driver focus-checks on this exact name (safety)
entry = tk.Entry(root, width=80, font=("monospace", 16))
entry.pack(padx=8, pady=8)
entry.focus_set()
root.geometry("760x70+120+120")


def dump(_evt=None):
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(entry.get())
    root.destroy()


root.bind("<Return>", dump)
root.after(15000, dump)                  # never hang the test
root.mainloop()
