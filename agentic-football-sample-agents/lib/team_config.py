"""Team identity — EDIT THIS to match what you set in the Player Portal.

Coach messages are heard by ALL 10 players, opponents included, and the
opponent coach's messages also land in OUR teamChat. So our agents only obey
messages that contain our CODEWORD. Keep it secret, change it if needed.

How to coach:  "DNP7 Kylian shoot now"   -> only Kylian acts on it
               "DNP7 everyone defend deep" -> whole team
"""

CODEWORD = "DNP7"

# Player names exactly as on the My Team page (index 0 = GK)
PLAYER_NAMES = {
    0: "Gardien",
    1: "Defenseur",
    2: "Milieu",
    3: "Attaquant1",
    4: "Attaquant2",
}
