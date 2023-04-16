#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
#~ import time
import tempfile
import logging

import tkinter as tk

_DEBUG = True

opj = os.path.join

WIN32 = sys.platform == "win32"
LINUX = sys.platform == "linux"
tmpdir = tempfile.gettempdir()

my_file_name = os.path.abspath(__file__)
if os.path.islink(my_file_name):
	my_file_name = os.readlink(my_file_name)
my_folder = os.path.dirname(my_file_name)
my_name = os.path.splitext(os.path.basename(my_file_name))[0]

#~ log|

class Application(tk.Frame):
	def __init__(self, master=None):
		super().__init__(master)
		self.master = master
		self.pack(side="top", fill="both", expand=True)
		self.create_widgets()
		self.bind("<KeyPress>", self.on_keypress)
		self.focus()

	def on_keypress(self, e):
		#~ print(e)
		if e.keysym == "Escape":
			self.master.destroy()

	def create_widgets(self):
		self.uf = tk.Frame(self)
		self.uf.pack(side="top", fill="x", expand=False)

		self.lClock = tk.Label(self.uf, text="<lClock>"
			, font=("a_LCDNova", 56))
		self.lClock.pack(side="right", anchor="n")

		self.lStatus = tk.Label(self.uf, text="<lStatus><lStatus>"
			, font=("Impact", 48))
		self.lStatus.pack(side="right", fill="both", expand=True)

		self.mf = tk.Frame(self)
		self.mf.pack(side="top", fill="x", expand=False)

		self.lVideoTitle = tk.Label(self.mf, text="<lVideoTitle>\n2nd line"
			, relief="groove", bd=2, font=("Impact", 48))
		self.lVideoTitle.pack(side="top", fill="x", expand=True)

		self.lf = tk.Frame(self)
		self.lf.pack(side="top", fill="both", expand=True)

		self.lvVideos = tk.Variable(value=[c for c in "abcd0123456789"])
		self.lbVideos = tk.Listbox(self.lf, listvariable=self.lvVideos
			, justify="center", font=("Liberation Serif", 24))
		self.lbVideos.pack(side="top", fill="both", expand=True)
		self.lbVideos.itemconfig(1, bg="#800000")

		#~ self.hi_there = tk.Button(self)
		#~ self.hi_there["text"] = "Hello World\n(click me)"
		#~ self.hi_there.pack(side="top")

		#~ self.quit = tk.Button(self, text="QUIT", fg="red"
			#~ , command=self.master.destroy)
		#~ self.quit.pack(side="bottom")


def main():
	#~ logi("Started")
	#~ for var, value in globals().items():
		#~ logd("%16s = %s", var, value)

	root = tk.Tk()
	root.geometry("512x384+100+100")
	app = Application(root)
	app.mainloop()

	#~ logi("Finished")


if __name__ == '__main__':
	main()
