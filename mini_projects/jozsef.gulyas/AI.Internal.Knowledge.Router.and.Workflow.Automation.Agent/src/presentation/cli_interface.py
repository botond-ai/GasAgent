from presentation.display_writer_interface import DisplayWriterInterface

class CliInterface(DisplayWriterInterface):
    def write(self, content: str) -> None:
        print(content)