import os
from interface import create_ui

def main():
    demo = create_ui()
    demo.queue().launch(server_name="0.0.0.0", debug=True, inbrowser=True)

if __name__ == "__main__":
    main()