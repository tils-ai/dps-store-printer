import fonts

# GUI 모듈 import 전에 폰트를 프로세스에 등록
fonts.register()

from gui import AgentApp


def main():
    app = AgentApp()
    app.mainloop()


if __name__ == "__main__":
    main()
