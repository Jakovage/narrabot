from pyt2s.services import stream_elements
from enum import Enum as __enum__

class Voice(__enum__):
    Joanna = "Joanna"         # US Female (neutral, very common default)
    Matthew = "Matthew"       # US Male (neutral, warm tone)
    Amy = "Amy"               # UK Female (friendly, clear)
    Brian = "Brian"           # UK Male (confident, polished)
    Emma = "Emma"             # UK Female (bright, youthful)
    Raveena = "Raveena"       # Indian English Female
    Justin = "Justin"         # US Child Male (younger voice)
    Salli = "Salli"           # US Female (crisp, expressive)
    Ivy = "Ivy"               # US Child Female
    Kimberly = "Kimberly"     # US Female (mature, formal)
    Kendra = "Kendra"         # US Female (smooth, natural)
    Joey = "Joey"             # US Male (casual, expressive)
    Nicole = "Nicole"         # Australian Female
    Russell = "Russell"       # Australian Male
    Geraint = "Geraint"       # Welsh Male (UK regional)
    Zhiyu = "Zhiyu"           # Chinese Mandarin Female
    Takumi = "Takumi"         # Japanese Male
    Mizuki = "Mizuki"         # Japanese Female
    Seoyeon = "Seoyeon"       # Korean Female
    Astrid = "Astrid"         # Swedish Female
    Hans = "Hans"             # German Male
    Marlene = "Marlene"       # German Female
    Ines = "Ines"             # Portuguese (EU) Female
    Penelope = "Penelope"     # Spanish (US) Female
    Carmen = "Carmen"         # Spanish (EU) Female