import re
import requests

from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd
from enum import Enum


class Ergebnis(str, Enum):

    WHITE_WIN = "1-0"
    BLACK_WIN = "0-1"

    DRAW = "1/2-1/2"

    WHITE_FORFEIT_WIN = "+--"
    BLACK_FORFEIT_WIN = "--+"

    DOUBLE_FORFEIT = "0-0"

    @classmethod
    def from_string(cls, value: str):

        normalized = value.replace("½", "1/2").replace(" ", "")

        mapping = {
            "1-0": cls.WHITE_WIN,
            "0-1": cls.BLACK_WIN,
            "1/2-1/2": cls.DRAW,
            "+--": cls.WHITE_FORFEIT_WIN,
            "--+": cls.BLACK_FORFEIT_WIN,
            "0-0": cls.DOUBLE_FORFEIT,
        }

        if normalized not in mapping:

            raise ValueError(f"Unbekanntes Ergebnis: {value}")

        return mapping[normalized]

    def flipped(self):

        mapping = {
            Ergebnis.WHITE_WIN: Ergebnis.BLACK_WIN,
            Ergebnis.BLACK_WIN: Ergebnis.WHITE_WIN,
            Ergebnis.WHITE_FORFEIT_WIN: Ergebnis.BLACK_FORFEIT_WIN,
            Ergebnis.BLACK_FORFEIT_WIN: Ergebnis.WHITE_FORFEIT_WIN,
            Ergebnis.DRAW: Ergebnis.DRAW,
            Ergebnis.DOUBLE_FORFEIT: Ergebnis.DOUBLE_FORFEIT,
        }

        return mapping[self]

    def points_white(self):

        mapping = {
            Ergebnis.WHITE_WIN: 1.0,
            Ergebnis.BLACK_WIN: 0.0,
            Ergebnis.DRAW: 0.5,
            Ergebnis.WHITE_FORFEIT_WIN: 1.0,
            Ergebnis.BLACK_FORFEIT_WIN: 0.0,
            Ergebnis.DOUBLE_FORFEIT: 0.0,
        }

        return mapping[self]

    def points_black(self):

        return 1.0 - self.points_white()

    def __str__(self):

        return self.value


# ============================================================
# Partie
# ============================================================


@dataclass
class Partie:
    round_number: int
    board_number: int

    white: str
    black: str

    id_white: Optional[str]
    id_black: Optional[str]

    result: str

    def export(self):
        return {
            "Round": self.round_number,
            "Board": self.board_number,
            "White": self.white,
            "Black": self.black,
            "IDWhite": self.id_white,
            "IDBlack": self.id_black,
            "Result": self.result,
        }

    def export(self):

        return {
            "Round": self.round_number,
            "Board": self.board_number,
            "White": self.white,
            "Black": self.black,
            "IDWhite": self.id_white,
            "IDBlack": self.id_black,
            "Result": self.result,
        }

    def to_dataframe(self):

        return pd.DataFrame([self.export()])


# ============================================================
# Mannschaftskampf
# ============================================================


@dataclass
class Mannschaftskampf:
    round_number: int

    team_a: str
    team_b: str

    partien: List[Partie] = field(default_factory=list)

    @classmethod
    def create_from_rows(
        cls,
        header_row,
        game_rows,
        round_number: int,
    ):

        tds = header_row.find_all("td")

        # ----------------------------------------------------
        # Mannschaftsnamen
        # ----------------------------------------------------

        team_a = tds[1].get_text(strip=True)
        team_b = tds[3].get_text(strip=True)

        mk = cls(
            round_number=round_number,
            team_a=team_a,
            team_b=team_b,
        )

        # ----------------------------------------------------
        # Einzelpartien
        # ----------------------------------------------------

        for row in game_rows:

            cells = row.find_all("td")

            # --------------------------------------------
            # Brettnummer
            # --------------------------------------------

            try:
                board_number = int(cells[0].get_text(strip=True))
            except:
                continue

            # ----------------------------------------------------
            # 2 mögliche Layouts:
            #
            # MIT ELO  -> 11 TDs
            # OHNE ELO -> 9 TDs
            # ----------------------------------------------------

            if len(cells) >= 11:

                # MIT ELO

                player_left = cells[2].get_text(strip=True)
                player_right = cells[7].get_text(strip=True)

                raw_result = cells[10].get_text(strip=True)

            else:

                # OHNE ELO

                player_left = cells[2].get_text(strip=True)
                player_right = cells[6].get_text(strip=True)

                raw_result = cells[8].get_text(strip=True)

            # --------------------------------------------
            # DWZ IDs
            # --------------------------------------------

            id_left = None
            id_right = None

            dwz_links = row.select('a[href*="zps="]')

            if len(dwz_links) >= 2:

                href_left = dwz_links[0]["href"]
                href_right = dwz_links[1]["href"]

                match_left = re.search(r"zps=([\d\-]+)", href_left)

                match_right = re.search(r"zps=([\d\-]+)", href_right)

                if match_left:
                    id_left = match_left.group(1)

                if match_right:
                    id_right = match_right.group(1)

            # --------------------------------------------
            # Ergebnis
            # --------------------------------------------

            result = Ergebnis.from_string(raw_result)

            # --------------------------------------------
            # Farben
            # --------------------------------------------

            if board_number % 2 == 1:

                # Team A hat Schwarz

                white = player_right
                black = player_left

                id_white = id_right
                id_black = id_left

                # Ergebnis umdrehen,
                # da Ergebnis aus linker Sicht kommt
                result = result.flipped()

            else:

                # Team A hat Weiß

                white = player_left
                black = player_right

                id_white = id_left
                id_black = id_right

            partie = Partie(
                round_number=round_number,
                board_number=board_number,
                white=white,
                black=black,
                id_white=id_white,
                id_black=id_black,
                result=result,
            )

            mk.partien.append(partie)
        return mk

    def export(self):

        result = []

        for partie in self.partien:

            row = partie.export()

            row["TeamA"] = self.team_a
            row["TeamB"] = self.team_b

            result.append(row)

        return result

    def to_dataframe(self):

        return pd.DataFrame(self.export())


# ============================================================
# Runde
# ============================================================


@dataclass
class Runde:
    round_number: int

    mannschaftskaempfe: List[Mannschaftskampf] = field(default_factory=list)

    @classmethod
    def create_from_soup(
        cls,
        soup: BeautifulSoup,
        round_number: int,
    ):

        runde = cls(round_number=round_number)

        # --------------------------------------------------------
        # Rundentitel finden
        # --------------------------------------------------------

        round_header = soup.find("th", id=f"tr{round_number}")

        if round_header is None:
            return runde

        # --------------------------------------------------------
        # Tabelle der Runde
        # --------------------------------------------------------

        table = round_header.find_parent("table")

        if table is None:
            return runde

        rows = table.find_all("tr")

        # --------------------------------------------------------
        # Nur Zeilen dieser Runde sammeln
        # --------------------------------------------------------

        current_header = None
        current_games = []

        inside_round = False

        for row in rows:

            # --------------------------------------------
            # Start der Runde
            # --------------------------------------------

            th = row.find("th")

            if th:

                th_id = th.get("id", "")

                # Start unserer Runde
                if th_id == f"tr{round_number}":
                    inside_round = True
                    continue

                # nächste Runde beginnt
                if inside_round and th_id.startswith("tr"):
                    break

            if not inside_round:
                continue

            classes = row.get("class", [])

            # --------------------------------------------
            # Mannschaftskampf Header
            # --------------------------------------------

            if "begegnung" in classes and "mannschaftTop" not in classes:

                # alten Kampf speichern
                if current_header:

                    mk = Mannschaftskampf.create_from_rows(
                        current_header, current_games, round_number
                    )

                    if len(mk.partien) > 0:
                        runde.mannschaftskaempfe.append(mk)

                current_header = row
                current_games = []

                continue

            # --------------------------------------------
            # Einzelpartie
            # --------------------------------------------

            classes = row.get("class", [])

            # mannschaftTop ignorieren
            if "mannschaftTop" in classes:
                continue

            cells = row.find_all("td")

            if len(cells) < 8:
                continue

            # Erste Zelle muss Brettnummer sein
            board_text = cells[0].get_text(strip=True)

            if not board_text.isdigit():
                continue

            # Zusätzlich:
            # echte Partiezeilen enthalten KEIN "DWZ"
            row_text = row.get_text(" ", strip=True)

            if "DWZ" in row_text:
                continue

            current_games.append(row)
        # --------------------------------------------------------
        # letzten Kampf speichern
        # --------------------------------------------------------

        if current_header:

            mk = Mannschaftskampf.create_from_rows(
                current_header, current_games, round_number
            )

            if len(mk.partien) > 0:
                runde.mannschaftskaempfe.append(mk)

        return runde

    def export(self):

        result = []

        for mk in self.mannschaftskaempfe:

            result.extend(mk.export())

        return result

    def to_dataframe(self):

        df = pd.DataFrame(self.export())

        if len(df) == 0:
            return df

        # Runde vorne einsortieren
        cols = list(df.columns)

        cols.remove("Round")

        cols = ["Round"] + cols

        return df[cols]


# ============================================================
# Saison
# ============================================================


@dataclass
class Saison:
    name: str

    runden: List[Runde] = field(default_factory=list)

    @classmethod
    def create_from_hyperlink(
        cls,
        hyperlink: str,
    ):

        response = requests.get(hyperlink)

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # ----------------------------------------------------
        # Saisonname
        # ----------------------------------------------------

        title = soup.find("h1")

        saison_name = title.get_text(strip=True)

        saison = cls(name=saison_name)

        # ----------------------------------------------------
        # Rundenzahl bestimmen
        # ----------------------------------------------------

        round_links = soup.find_all("a", href=re.compile(r"runde=\d+"))

        round_numbers = []

        for link in round_links:

            href = link.get("href", "")

            match = re.search(r"runde=(\d+)", href)

            if match:
                round_numbers.append(int(match.group(1)))

        round_numbers = sorted(list(set(round_numbers)))

        # ----------------------------------------------------
        # Runden laden
        # ----------------------------------------------------

        for round_number in round_numbers:

            print(f"Lade Runde {round_number}")

            runde = Runde.create_from_soup(soup, round_number)

            saison.runden.append(runde)

        return saison

    def export(self):

        result = []

        for runde in self.runden:

            result.extend(runde.export())

        return result

    def to_dataframe(self):

        df = pd.DataFrame(self.export())

        if len(df) == 0:
            return df

        # Schöne Spaltenreihenfolge

        preferred_order = [
            "Round",
            "Board",
            "TeamA",
            "TeamB",
            "White",
            "Black",
            "IDWhite",
            "IDBlack",
            "Result",
        ]

        existing_cols = [c for c in preferred_order if c in df.columns]

        remaining_cols = [c for c in df.columns if c not in existing_cols]

        return df[existing_cols + remaining_cols]

    def to_csv(
        self,
        path: str,
        sep: str = ";",
    ):

        df = self.to_dataframe()

        df.to_csv(path, sep=sep, index=False, encoding="utf-8")


if __name__ == "__main__":
    saison = Saison.create_from_hyperlink(
        "https://www.ligamanager.schachbund-bayern.de/bsb/ergebnisse/spielplan.htm?ligaId=2489"
    )
    saison.to_csv("saisontest.csv")
    saison2 = Saison.create_from_hyperlink(
        "https://www.ligamanager.schachbund-bayern.de/mfr-ost/ergebnisse/spielplan.htm?ligaId=2451"
    )
    saison2.to_csv("saison2test.csv")
    print(saison2)
