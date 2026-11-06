"""Track separate fruit detections within one camera's capture zone."""

from dataclasses import dataclass


def _center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _match_score(old, new):
    ox, oy = _center(old)
    nx, ny = _center(new)
    distance = ((ox - nx) ** 2 + (oy - ny) ** 2) ** 0.5
    old_size = max(old[2] - old[0], old[3] - old[1])
    new_size = max(new[2] - new[0], new[3] - new[1])
    if min(old_size, new_size) == 0 or max(old_size, new_size) / min(old_size, new_size) > 2:
        return None
    max_distance = max(35, 0.55 * max(old_size, new_size))
    if distance > max_distance:
        return None
    return 1 - distance / max_distance


@dataclass
class FruitTrack:
    track_id: int
    box: tuple
    first_seen: float
    last_seen: float
    photographed: bool = False
    best_frame: object = None
    best_box: tuple = None
    best_score: float = -1.0


class FruitTracker:
    def __init__(self, missing_seconds=1.5):
        self.missing_seconds = missing_seconds
        self.tracks = {}
        self.next_id = 1

    def update(self, boxes, now):
        """Return (track, box) pairs for currently detected fruits."""
        self.tracks = {
            track_id: track for track_id, track in self.tracks.items()
            if now - track.last_seen < self.missing_seconds
        }
        options = []
        for track_id, track in self.tracks.items():
            for box_index, box in enumerate(boxes):
                score = _match_score(track.box, box)
                if score is not None:
                    options.append((score, track_id, box_index))
        matched_tracks = set()
        matched_boxes = set()
        assignments = []
        for _, track_id, box_index in sorted(options, reverse=True):
            if track_id in matched_tracks or box_index in matched_boxes:
                continue
            matched_tracks.add(track_id)
            matched_boxes.add(box_index)
            assignments.append((self.tracks[track_id], boxes[box_index]))
        for box_index, box in enumerate(boxes):
            if box_index not in matched_boxes:
                track = FruitTrack(self.next_id, box, now, now)
                self.tracks[self.next_id] = track
                self.next_id += 1
                assignments.append((track, box))
        for track, box in assignments:
            track.box = box
            track.last_seen = now
        return assignments
