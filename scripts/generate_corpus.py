#!/usr/bin/env python3
import json
import random

random.seed(42)

short_phrases = [
    "This movie was fantastic and emotional.",
    "Terrible plot and boring acting throughout.",
    "Great direction and awesome soundtrack.",
    "I disliked the slow pacing immensely.",
    "An instant classic that everyone should see.",
    "Disappointing experience, would not recommend.",
    "Brilliant acting and stunning visuals.",
    "Complete waste of money and time.",
    "Loved every single minute of this.",
    "Horrible script and painful execution.",
]

medium_phrases = [
    "The cinematography was breathtaking, capturing every landscape with vibrant color and depth, while the soundtrack complemented the emotional weight of every key scene.",
    "Although the lead actor tried his best, the messy script and weak character development prevented the film from reaching its full potential, leaving viewers dissatisfied.",
    "A gripping psychological thriller that keeps you on the edge of your seat from the opening sequence to the final shocking twist at the end.",
    "Despite high expectations, the film suffered from poor editing choices, awkward dialogue transitions, and an abrupt conclusion that felt completely unearned.",
]

long_phrases = [
    "From beginning to end, this sweeping cinematic masterpiece weaves together themes of resilience, friendship, and heartbreak. The director's meticulous attention to historical detail, combined with power-packed performances by the entire ensemble cast, elevates the storytelling to unprecedented heights. Every musical cue accentuates the tension, while the stunning visual effects create an immersive world that lingers in your mind long after the credits roll.",
    "A catastrophic failure on nearly every creative front, failing to deliver a coherent narrative despite a bloated budget and star-studded cast. The pacing drags endlessly through meaningless subplots, while key character motivations remain utterly unexplained throughout the runtime. Viewers hoping for compelling action or clever dialogue will find only uninspired cliches and flat set-pieces.",
]

output_file = "benchmarks/corpus.jsonl"

records = []
for i in range(1, 1001):
    r = random.random()
    if r < 0.60:
        text = random.choice(short_phrases)
    elif r < 0.90:
        text = random.choice(medium_phrases)
    else:
        text = random.choice(long_phrases)
    records.append({"id": i, "text": text})

with open(output_file, "w") as f:
    for rec in records:
        f.write(json.dumps(rec) + "\n")

print(f"Generated 1000 corpus entries in {output_file}")
