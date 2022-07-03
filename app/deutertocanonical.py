from rich import table
from typing import Dict

DEUT_SET: Dict[str, str] = {"1ES": "Trzecia Księga Ezdrasza", "2ES": "Czwarta Księga Ezdrasza",
                            "TOB": "Księga Tobiasza", "JDT": "Księga Judyty", "SIR": "Księga Syracydesa (Eklezjastyka)", "BAR": "Barucha",
                            "ESG": "Greckie rozdziały księgi Estery",
                            "WIS": "Księga mądrości (mądrości Salomona)", "MAN": "Modlitwa Manassesa (Rozszerzenie 2 Kronik 33, 11)",
                            "S3Y": "Greckie fragmenty księgi Daniela (pieśń Azariasza i pieśń trojga z pieca, koniec 3 rozdziału)",
                            "SUS": "Greckie fragmenty księgi Daniela (Historia Zuzanny, rozdział 13)",
                            "BEL": "Greckie fragmenty księgi Daniela (Zniszczenie Bala i smoka/węża, rozdział 14)",
                            "1MA": "Pierwsza Machabejska", "2MA": "Druga Machabejska"}


def get_table() -> table.Table:
    # define deuterocanonical books
    deut_table: table.Table = table.Table(show_lines=True, title="Księgi Deuterokanoniczne")  # .grid(pad_edge=True)
    deut_table.add_column("Siglum")
    deut_table.add_column("Opis")
    [deut_table.add_row(key, value) for key, value in DEUT_SET.items()]
    return deut_table