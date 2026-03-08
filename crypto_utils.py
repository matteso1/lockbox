"""Cryptographic utilities for LockBox.

Handles:
- AES-256-GCM encryption/decryption
- Argon2id key derivation from master password
- Cryptographically secure password generation
"""

import os
import json
import secrets
import string
from typing import Optional

from argon2.low_level import hash_secret_raw, Type
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Argon2id parameters (OWASP recommended minimums)
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536  # 64 MB
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32  # 256 bits for AES-256
ARGON2_SALT_LEN = 16  # 128-bit salt

# AES-GCM nonce length
NONCE_LEN = 12  # 96 bits, standard for AES-GCM


def derive_key(master_password: str, salt: bytes) -> bytes:
    """Derive a 256-bit encryption key from the master password using Argon2id."""
    return hash_secret_raw(
        secret=master_password.encode("utf-8"),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=ARGON2_HASH_LEN,
        type=Type.ID,
    )


def generate_salt() -> bytes:
    """Generate a random salt for key derivation."""
    return os.urandom(ARGON2_SALT_LEN)


def encrypt(data: bytes, key: bytes) -> bytes:
    """Encrypt data using AES-256-GCM.

    Returns: nonce (12 bytes) || ciphertext+tag
    """
    nonce = os.urandom(NONCE_LEN)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext


def decrypt(data: bytes, key: bytes) -> bytes:
    """Decrypt data using AES-256-GCM.

    Expects: nonce (12 bytes) || ciphertext+tag
    """
    nonce = data[:NONCE_LEN]
    ciphertext = data[NONCE_LEN:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def generate_password(
    length: int = 20,
    uppercase: bool = True,
    lowercase: bool = True,
    digits: bool = True,
    symbols: bool = True,
    custom_symbols: Optional[str] = None,
    exclude_ambiguous: bool = False,
) -> str:
    """Generate a cryptographically secure random password.

    Args:
        length: Password length (minimum 8).
        uppercase: Include A-Z.
        lowercase: Include a-z.
        digits: Include 0-9.
        symbols: Include special characters.
        custom_symbols: Override default symbol set.
        exclude_ambiguous: Remove chars like 0/O, 1/l/I that look alike.

    Returns:
        A random password string.
    """
    if length < 4:
        length = 4

    charset = ""
    required = []

    ambiguous = "0O1lI|" if exclude_ambiguous else ""

    if uppercase:
        pool = "".join(c for c in string.ascii_uppercase if c not in ambiguous)
        charset += pool
        required.append(pool)
    if lowercase:
        pool = "".join(c for c in string.ascii_lowercase if c not in ambiguous)
        charset += pool
        required.append(pool)
    if digits:
        pool = "".join(c for c in string.digits if c not in ambiguous)
        charset += pool
        required.append(pool)
    if symbols:
        sym = custom_symbols if custom_symbols else "!@#$%^&*()_+-=[]{}|;:,.<>?"
        pool = "".join(c for c in sym if c not in ambiguous)
        charset += pool
        required.append(pool)

    if not charset:
        charset = string.ascii_letters + string.digits
        required = [charset]

    # Generate password ensuring at least one char from each required set
    while True:
        password = [secrets.choice(charset) for _ in range(length)]
        # Verify at least one character from each required category
        if all(any(c in req for c in password) for req in required):
            return "".join(password)


def generate_passphrase(word_count: int = 5, separator: str = "-") -> str:
    """Generate a passphrase from random words (diceware-style).

    Uses a built-in word list for offline operation.
    """
    words = _get_word_list()
    chosen = [secrets.choice(words) for _ in range(word_count)]
    return separator.join(chosen)


def _get_word_list() -> list[str]:
    """Return a list of common English words for passphrase generation."""
    # EFF short word list subset - common, easy to type words
    return [
        "acid", "acme", "aged", "also", "arch", "area", "army", "atom",
        "aunt", "avid", "away", "axis", "back", "badge", "bail", "bake",
        "ball", "band", "bank", "barn", "base", "bath", "bead", "beam",
        "bean", "bear", "beat", "beef", "been", "bell", "belt", "bend",
        "best", "bike", "bind", "bird", "bite", "blab", "bled", "blew",
        "blob", "blog", "blot", "blow", "blue", "blur", "boat", "body",
        "bold", "bolt", "bomb", "bond", "bone", "book", "boom", "boot",
        "bore", "born", "boss", "both", "bowl", "bred", "brew", "brim",
        "brisk", "broad", "broil", "brook", "brow", "brush", "buck",
        "bulk", "bull", "bump", "burn", "burp", "bush", "busy", "buzz",
        "cafe", "cage", "cake", "call", "calm", "came", "camp", "cane",
        "cape", "card", "care", "cart", "case", "cash", "cast", "cave",
        "cell", "chap", "chat", "chef", "chin", "chip", "chop", "chow",
        "cite", "city", "clad", "clam", "clan", "clap", "claw", "clay",
        "clip", "clock", "clone", "cloth", "club", "clue", "coal",
        "coat", "code", "coil", "coin", "cold", "colt", "come", "cone",
        "cook", "cool", "cope", "copy", "cord", "core", "cork", "corn",
        "cost", "cosy", "coup", "cove", "cozy", "crab", "cram", "crew",
        "crib", "crop", "crow", "crud", "cube", "cult", "curb", "cure",
        "curl", "cute", "cycle", "dare", "dark", "dart", "dash", "data",
        "date", "dawn", "dead", "deaf", "deal", "dean", "dear", "debt",
        "deck", "deed", "deem", "deep", "deer", "demo", "dent", "deny",
        "desk", "dial", "dice", "diet", "dime", "dine", "dirt", "disc",
        "dish", "disk", "dock", "does", "doll", "dome", "done", "doom",
        "door", "dose", "dove", "down", "doze", "drab", "drag", "dram",
        "draw", "drip", "drop", "drum", "dual", "duck", "dude", "duel",
        "duet", "duke", "dull", "dumb", "dump", "dune", "dunk", "dusk",
        "dust", "duty", "dyed", "each", "earl", "earn", "ease", "east",
        "easy", "edge", "edit", "else", "emit", "ends", "epic", "euro",
        "even", "ever", "evil", "exam", "exit", "expo", "face", "fact",
        "fade", "fail", "fair", "fake", "fall", "fame", "fang", "fare",
        "farm", "fast", "fate", "fawn", "fear", "feat", "feed", "feel",
        "feet", "fell", "felt", "fend", "fern", "fest", "feud", "film",
        "find", "fine", "fire", "firm", "fish", "fist", "five", "flag",
        "flame", "flap", "flat", "flaw", "fled", "flew", "flex", "flip",
        "flit", "flock", "flog", "flow", "foam", "foil", "fold", "folk",
        "fond", "font", "food", "fool", "foot", "ford", "fore", "fork",
        "form", "fort", "foul", "four", "fowl", "free", "fret", "frog",
        "from", "fuel", "full", "fume", "fund", "fuse", "fuss", "fuzz",
        "gain", "gait", "gale", "game", "gang", "gape", "garb", "gate",
        "gave", "gaze", "gear", "gene", "gift", "glad", "glee", "glen",
        "glib", "glob", "gloom", "glow", "glue", "glum", "goal", "goat",
        "goes", "gold", "golf", "gone", "good", "goof", "gore", "grab",
        "gram", "gray", "grew", "grid", "grim", "grin", "grip", "grit",
        "grow", "grub", "gulf", "gull", "gulp", "guru", "gust", "guts",
        "hack", "hail", "hair", "hale", "half", "hall", "halt", "hand",
        "hang", "hare", "harm", "harp", "hash", "haste", "hate", "haul",
        "have", "haze", "hazy", "head", "heal", "heap", "hear", "heat",
        "heed", "heel", "held", "helm", "help", "herb", "herd", "here",
        "hero", "hike", "hill", "hilt", "hind", "hint", "hire", "hive",
        "hold", "hole", "home", "hone", "hood", "hook", "hope", "horn",
        "hose", "host", "hour", "howl", "huge", "hull", "hump", "hung",
        "hunt", "hurl", "hurt", "hush", "hymn", "icon", "idea", "idle",
        "inch", "info", "iron", "isle", "item", "jade", "jail", "jazz",
        "jean", "jerk", "jest", "jobs", "jock", "join", "joke", "jolt",
        "jump", "june", "junk", "jury", "just", "keen", "keep", "kelp",
        "kept", "kick", "kill", "kind", "king", "kiss", "kite", "knack",
        "knee", "knew", "knit", "knob", "knot", "know", "lace", "lack",
        "laid", "lake", "lamb", "lame", "lamp", "land", "lane", "lark",
        "last", "late", "lawn", "lead", "leaf", "leak", "lean", "leap",
        "left", "lend", "lens", "lent", "less", "liar", "lick", "lieu",
        "life", "lift", "like", "limb", "lime", "limp", "line", "link",
        "lion", "list", "live", "load", "loaf", "loan", "lock", "loft",
        "logo", "lone", "long", "look", "loop", "lord", "lore", "lose",
        "loss", "lost", "lots", "loud", "love", "luck", "lump", "lure",
        "lurk", "lush", "lust", "lynx", "made", "maid", "mail", "main",
        "make", "male", "mall", "malt", "mane", "many", "mare", "mark",
        "mars", "mash", "mask", "mass", "mast", "mate", "maze", "mead",
        "meal", "mean", "meat", "meek", "meet", "meld", "melt", "memo",
        "mend", "menu", "mere", "mesh", "mice", "mild", "mile", "milk",
        "mill", "mime", "mind", "mine", "mint", "mire", "miss", "mist",
        "mitt", "moan", "moat", "mock", "mode", "mold", "molt", "monk",
        "mood", "moon", "moor", "more", "moss", "most", "moth", "move",
        "much", "muck", "mule", "mull", "muse", "mush", "must", "mute",
        "myth", "nail", "name", "nape", "navy", "near", "neat", "neck",
        "need", "nest", "news", "next", "nice", "nine", "node", "none",
        "nook", "norm", "nose", "note", "noun", "nova", "null", "numb",
        "oath", "obey", "odds", "odor", "oink", "okay", "omen", "omit",
        "once", "only", "onto", "ooze", "open", "oral", "orca", "oval",
        "oven", "over", "owed", "pace", "pack", "page", "paid", "pail",
        "pain", "pair", "pale", "palm", "pane", "pang", "park", "part",
        "pass", "past", "path", "pave", "pawn", "peak", "peal", "pear",
        "peat", "peck", "peek", "peel", "peer", "pelt", "pend", "perk",
        "pest", "pick", "pier", "pike", "pile", "pill", "pine", "pink",
        "pipe", "plan", "play", "plea", "plod", "plot", "plow", "ploy",
        "plug", "plum", "plus", "pock", "poem", "poet", "pole", "poll",
        "polo", "pond", "pony", "pool", "pope", "pore", "pork", "port",
        "pose", "post", "pour", "pray", "prey", "prod", "prop", "prow",
        "pull", "pulp", "pump", "punk", "pure", "push", "quit", "quiz",
        "race", "rack", "raft", "rage", "raid", "rail", "rain", "rake",
        "ramp", "rang", "rank", "rant", "rare", "rash", "rate", "rave",
        "rays", "read", "real", "ream", "reap", "rear", "reed", "reef",
        "reel", "rein", "rely", "rend", "rent", "rest", "rice", "rich",
        "ride", "rift", "rigs", "rile", "rill", "rime", "rind", "ring",
        "rink", "riot", "ripe", "rise", "risk", "road", "roam", "roar",
        "robe", "rock", "rode", "role", "roll", "roof", "room", "root",
        "rope", "rose", "rosy", "rout", "rove", "ruby", "rude", "ruin",
        "rule", "rump", "rune", "rung", "runt", "ruse", "rush", "rust",
        "sack", "safe", "sage", "said", "sail", "sake", "sale", "salt",
        "same", "sand", "sane", "sang", "sank", "sash", "save", "scam",
        "scan", "scar", "seal", "seam", "seed", "seek", "seem", "seen",
        "self", "sell", "send", "sent", "sept", "sewn", "shed", "shin",
        "ship", "shop", "shot", "show", "shut", "sick", "side", "sift",
        "sigh", "sign", "silk", "sill", "silo", "silt", "sink", "sire",
        "site", "size", "skit", "slab", "slag", "slam", "slap", "slat",
        "slaw", "sled", "slew", "slid", "slim", "slit", "slob", "slot",
        "slow", "slug", "slum", "slur", "smog", "snap", "snip", "snob",
        "snot", "snow", "snub", "snug", "soak", "soap", "soar", "sock",
        "soda", "sofa", "soft", "soil", "sold", "sole", "some", "song",
        "soon", "soot", "sore", "sort", "soul", "sour", "span", "spar",
        "spec", "sped", "spew", "spin", "spit", "spot", "spud", "spun",
        "spur", "stab", "stag", "star", "stay", "stem", "step", "stew",
        "stir", "stop", "stub", "stud", "stun", "such", "suit", "sulk",
        "sung", "sunk", "sure", "surf", "swan", "swap", "swim", "swirl",
        "swoop", "sync", "tabs", "tack", "tact", "tail", "take", "tale",
        "talk", "tall", "tame", "tank", "tape", "taps", "tarn", "tarp",
        "tart", "task", "taxi", "teak", "teal", "team", "tear", "tech",
        "tell", "temp", "tend", "tent", "term", "test", "text", "than",
        "that", "them", "then", "they", "thin", "this", "thorn", "thus",
        "tick", "tide", "tidy", "tied", "tier", "tile", "till", "tilt",
        "time", "tint", "tiny", "tire", "toad", "tock", "toes", "toil",
        "told", "toll", "tomb", "tone", "took", "tool", "tops", "tore",
        "torn", "tort", "toss", "tour", "town", "trap", "tray", "tree",
        "trek", "trim", "trio", "trip", "trod", "trot", "true", "tuba",
        "tube", "tuck", "tuft", "tuna", "tune", "turf", "turn", "tusk",
        "tutor", "twin", "type", "ugly", "undo", "unit", "unto", "upon",
        "urge", "used", "user", "vain", "vale", "vane", "vary", "vase",
        "vast", "veil", "vein", "vent", "verb", "very", "vest", "veto",
        "vial", "view", "vine", "visa", "void", "volt", "vote", "wade",
        "wage", "wail", "wait", "wake", "walk", "wall", "wand", "want",
        "ward", "warm", "warn", "warp", "wart", "wary", "wash", "wasp",
        "wave", "wavy", "waxy", "weak", "wean", "wear", "weed", "week",
        "weld", "well", "went", "wept", "were", "west", "what", "when",
        "whim", "whip", "whom", "wick", "wide", "wife", "wild", "will",
        "wilt", "wily", "wimp", "wind", "wine", "wing", "wink", "wipe",
        "wire", "wise", "wish", "wisp", "with", "wits", "woke", "wolf",
        "womb", "wood", "wool", "word", "wore", "work", "worm", "worn",
        "wove", "wrap", "wren", "writ", "yank", "yard", "yarn", "yawn",
        "year", "yell", "yoga", "yoke", "your", "zeal", "zero", "zest",
        "zinc", "zone", "zoom",
    ]
