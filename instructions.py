import tkinter as tk
from tkinter import messagebox

def show_message():
    message = "Ensure you are using Chrome version 114.\n\n" \
              "Enter the desired details as indicated.\n" \
              "A Chrome window will popup and will start the automations.\n" \
              "The automations depend on what you had input.\n" \
              "Please do not close the window until the process is finished."
    messagebox.showinfo("Message", message)

root = tk.Tk()
root.withdraw()  # Hide the main tkinter window

# Show the message box
show_message()

root.mainloop()
