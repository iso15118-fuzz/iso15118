import json
from collections import defaultdict

from iso15118.fuzzer.consts import KNOWN_MUTATION_COUNTER


def load_json_map(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return {int(k): v for k, v in data.items()}


def convert_mutation_counter(old_map, new_map, known_counter):
    reverse_new = defaultdict(list)
    for new_idx, loc in new_map.items():
        reverse_new[loc].append(new_idx)

    new_counter = defaultdict(int)
    for old_idx, count in known_counter.items():
        location = old_map.get(old_idx)
        if location is None:
            continue
        new_indices = reverse_new.get(location, [])
        for new_idx in new_indices:
            new_counter[new_idx] += count

    return dict(new_counter)


if __name__ == "__main__":
    old_map = load_json_map("old.json")
    new_map = load_json_map("new.json")
    new_counter = convert_mutation_counter(old_map, new_map, KNOWN_MUTATION_COUNTER)
    print("KNOWN_MUTATION_COUNTER =", new_counter)
