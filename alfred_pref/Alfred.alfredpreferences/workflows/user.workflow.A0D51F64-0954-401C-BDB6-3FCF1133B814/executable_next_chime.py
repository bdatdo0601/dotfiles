#!/usr/bin/env -S -P/Library/Developer/CommandLineTools/usr/bin:${PATH} python3

"""
Find the next calendar events with Chime details

Needs "brew install ical-buddy".
"""

import datetime
import os
import os.path
import re
import site
import subprocess  # nosec
import sys
import time
from collections import OrderedDict

site.addsitedir("vendor")

from workflow import Workflow3


class JoinableEvent:
    """Represent an event Alfred can join."""

    def __init__(self, event_name, start_time, end_time, sort_time):
        self.event_name = re.sub(
            r"""(
                (fw|re|):
                |
                \[external\]
                |
                (invitation|confirmed):
                |
                \([a-z0-9_+-]+@[a-z0-9.-]+\)  # email address
                )""",
            "",
            event_name,
            flags=re.IGNORECASE | re.VERBOSE,
        ).strip()
        self.start_time = start_time
        self.end_time = end_time
        self.sort_time = sort_time
        if self.sort_time:
            self.start_datetime = datetime.datetime.strptime(
                self.sort_time, "%H:%M"
            ).time()
        else:
            self.start_datetime = None

    def description(self):
        raise NotImplementedError

    def url(self):
        raise NotImplementedError

    def icon(self):
        raise NotImplementedError

    def time_field(self):
        now = datetime.datetime.now().time()
        try:
            if self.start_datetime:
                if self.start_datetime < now:
                    return f"ending at {self.end_time}"
        except Exception:
            pass
        if self.start_time is None:
            return ""
        return f"starting at {self.start_time}"

    @staticmethod
    def _fix_description(text):
        return re.sub(r"  +", " ", text)


class ChimeEvent(JoinableEvent):
    """Represent a Chime event."""

    def __init__(
        self, event_name, start_time, end_time, sort_time, meeting_id, meeting_pin
    ):
        super().__init__(event_name, start_time, end_time, sort_time)
        self.meeting_id = meeting_id
        self.meeting_pin = meeting_pin

    def description(self):
        if self.meeting_id is not None:
            return self._fix_description(
                f"Join meeting {self.time_field()} with Chime ID {self.meeting_id}"
            )
        return self._fix_description(
            f"Join meeting {self.time_field()} with Chime PIN {self._format_chime_pin()}"
        )

    def url(self):
        if self.meeting_pin is not None:
            return f"chime://meeting?pin={self.meeting_pin}"
        return f"chime://meeting?pin={self.meeting_id}"

    def icon(self):
        return None  # default icon from Alfred

    def _format_chime_pin(self):
        chime_pin_str = str(self.meeting_pin)
        return "{} {} {}".format(
            chime_pin_str[0:4], chime_pin_str[4:6], chime_pin_str[6:]
        )

    def __repr__(self):
        return "chime: {} {}-{} ({}) id:{} pin:{}".format(
            self.event_name,
            self.start_time,
            self.end_time,
            self.sort_time,
            self.meeting_id,
            self.meeting_pin,
        )


class BroadcastEvent(JoinableEvent):
    """Represent a Broadcast event."""

    def __init__(self, event_name, start_time, end_time, sort_time, broadcast_url):
        super().__init__(event_name, start_time, end_time, sort_time)
        self.broadcast_url = broadcast_url

    def description(self):
        return self._fix_description(f"Open Livestreaming event {self.time_field()}")

    def url(self):
        return self.broadcast_url

    def icon(self):
        return "broadcast.png"


class TeamsEvent(JoinableEvent):
    """Represent a Teams event."""

    def __init__(self, event_name, start_time, end_time, sort_time, teams_url):
        super().__init__(event_name, start_time, end_time, sort_time)
        self.teams_url = teams_url

    def description(self):
        return self._fix_description("Join Teams meeting {}".format(self.time_field()))

    def url(self):
        return self.teams_url

    def icon(self):
        return "teams.png"


class MeetEvent(JoinableEvent):
    """Represent a Google Meet event."""

    def __init__(self, event_name, start_time, end_time, sort_time, meet_url):
        super().__init__(event_name, start_time, end_time, sort_time)
        if "@" in self.event_name:
            self.event_name = self.event_name.split("@")[0]
        self.meet_url = meet_url

    def description(self):
        return self._fix_description(
            "Join Google Meet meeting {}".format(self.time_field())
        )

    def url(self):
        return self.meet_url

    def icon(self):
        return "meet.png"


class ZoomEvent(JoinableEvent):
    """Represent a Zoom event."""

    def __init__(self, event_name, start_time, end_time, sort_time, zoom_url):
        super().__init__(event_name, start_time, end_time, sort_time)
        if "@" in self.event_name:
            self.event_name = self.event_name.split("@")[0]
        self.zoom_url = zoom_url

    def description(self):
        return self._fix_description("Join Zoom meeting {}".format(self.time_field()))

    def url(self):
        return self.zoom_url

    def icon(self):
        return "zoom.png"


class GoToMeetingEvent(JoinableEvent):
    """Represent a GoToMeeting event."""

    def __init__(self, event_name, start_time, end_time, sort_time, goto_url):
        super().__init__(event_name, start_time, end_time, sort_time)
        self.goto_url = goto_url

    def description(self):
        return self._fix_description("Join GoToMeeting {}".format(self.time_field()))

    def url(self):
        return self.goto_url

    def icon(self):
        return "gotomeeting.png"


class WebexEvent(JoinableEvent):
    """Represent a Webex event."""

    def __init__(self, event_name, start_time, end_time, sort_time, webex_url):
        super().__init__(event_name, start_time, end_time, sort_time)
        self.webex_url = webex_url

    def description(self):
        return self._fix_description("Join Webex meeting {}".format(self.time_field()))

    def url(self):
        return self.webex_url

    def icon(self):
        return "webex.png"


class CalendarScanner(object):
    def __init__(self):
        self.event_name = None
        self.input_filename = None
        self.events = {}
        self._reset()

    def _reset(self):
        self.meeting_pin = None
        self.meeting_id = None
        self.start_time = None
        self.end_time = None
        self.sort_time = None
        self.broadcast_url = None
        self.teams_url = None
        self.meet_url = None
        self.zoom_url = None
        self.goto_url = None
        self.webex_url = None

    def _save(self):
        if not self.event_name:
            raise RuntimeError("Bad event data")
        if self.meeting_id or self.meeting_pin:
            return ChimeEvent(
                self.event_name,
                self.start_time,
                self.end_time,
                self.sort_time,
                self.meeting_id,
                self.meeting_pin,
            )
        if self.broadcast_url:
            return BroadcastEvent(
                self.event_name,
                self.start_time,
                self.end_time,
                self.sort_time,
                self.broadcast_url,
            )
        if self.teams_url:
            return TeamsEvent(
                self.event_name,
                self.start_time,
                self.end_time,
                self.sort_time,
                self.teams_url,
            )
        if self.meet_url:
            return MeetEvent(
                self.event_name,
                self.start_time,
                self.end_time,
                self.sort_time,
                self.meet_url,
            )
        if self.zoom_url:
            return ZoomEvent(
                self.event_name,
                self.start_time,
                self.end_time,
                self.sort_time,
                self.zoom_url,
            )
        if self.goto_url:
            return GoToMeetingEvent(
                self.event_name,
                self.start_time,
                self.end_time,
                self.sort_time,
                self.goto_url,
            )
        if self.webex_url:
            return WebexEvent(
                self.event_name,
                self.start_time,
                self.end_time,
                self.sort_time,
                self.webex_url,
            )
        raise RuntimeError("Bad event data")

    @staticmethod
    def _first_valid_item(*args):
        for item in args:
            if item is not None:
                return item
        return None

    def get_events(self, wf):
        path_non_m1 = "/usr/local/bin/icalBuddy"
        path_m1 = "/opt/homebrew/opt/ical-buddy/bin/icalBuddy"
        if os.path.exists(path_non_m1):
            icalbuddy_path = path_non_m1
        elif os.path.exists(path_m1):
            icalbuddy_path = path_m1
        else:
            raise RuntimeError("Please `brew install ical-buddy`")
        if self.input_filename:
            # for testing
            with open(self.input_filename, "rb") as fh:
                output = fh.read().decode("utf-8")
        else:
            try:
                _output = subprocess.check_output(  # nosec
                    [
                        icalbuddy_path,
                        "-b",
                        "__start ",  # event "bullet" style
                        "-n",  # omit events earlier than now
                        "-ea",  # exclude all-day events
                        "-tf",  # force time format
                        "%H:%M",
                        "eventsToday",
                    ]
                )
            except OSError:
                wf.warn_empty("Please 'brew install ical-buddy'")
                wf.send_feedback()
                return
            except subprocess.CalledProcessError:
                wf.warn_empty(
                    "Error running icalBuddy; maybe no Calendar access granted in macOS?"
                )
                wf.send_feedback()
                return
            output = _output.decode(encoding="utf-8")

        events = {}

        for line in output.splitlines():
            line = line.rstrip()
            if line == "":
                continue
            matches = re.match(r"__start (?P<event>.+) \([^)]+\)", line)
            if matches:
                try:
                    events[self.event_name] = self._save()
                except RuntimeError:
                    pass
                self.event_name = matches.group("event")
                self._reset()
                continue

            matches = re.search(
                r"(?P<url>https://(broadcast|livestreaming\.corp)\.amazon\.com/live/[a-zA-Z0-9_.-]+)",
                line,
            )
            if matches:
                self.broadcast_url = matches.group("url")
                continue

            if not any([self.meeting_id, self.meeting_pin]):
                matches = re.search(
                    r"""(
                        chime.aws/(?P<pin>[a-zA-Z0-9._-]{12,35}|\b[0-9]{10}\b)
                        |
                        (?P<pin2>\b[0-9]{10})\#
                        |
                        (?P<pin3>[0-9]{4}\s[0-9]{2}\s[0-9]{4})
                        |
                        (?P<pin4>[0-9]{4}\s[0-9]{4}\s[0-9]{2})
                        )
                        """,
                    line,
                    re.VERBOSE,
                )
                if matches:
                    if self.event_name is not None:
                        pin = self._first_valid_item(
                            matches.group("pin"),
                            matches.group("pin2"),
                            matches.group("pin3"),
                            matches.group("pin4"),
                        )
                        if not pin:
                            continue
                        pin = pin.replace(" ", "")
                        if pin not in ["dialinnumbers"]:
                            if pin.isnumeric():
                                self.meeting_pin = pin
                            else:
                                self.meeting_id = pin
                    continue

            matches = re.match(
                r" {4}(?P<start>\d{1,2}:\d\d(?P<ampm> am| pm)?) - (?P<end>\d{1,2}:\d\d(?P<ampmend> am| pm)?)",
                line,
            )
            if matches:
                self.start_time = matches.group("start")
                self.end_time = matches.group("end")
                if matches.group("ampm"):
                    self.sort_time = time.strftime(
                        "%H:%M", time.strptime(self.start_time, "%I:%M %p")
                    )
                else:
                    self.sort_time = self.start_time
                continue

            matches = re.search(
                r"<(?P<url>https://teams.microsoft.com/l/meetup-join/[^>]+)>",
                line,
            )
            if matches:
                self.teams_url = matches.group("url")
                continue

            matches = re.search(
                r"(?P<url>https://meet.google.com/[a-z]{3}-[a-z]{4}-[a-z]{3})", line
            )
            if matches:
                self.meet_url = matches.group("url")
                continue

            matches = re.search(r"(?P<url>https://([a-z0-9]+.)?zoom.us/j/[0-9]+)", line)
            if matches:
                self.zoom_url = matches.group("url")
                continue

            matches = re.search(
                r"(?P<url>https://global.gotomeeting.com/join/\d{9})", line
            )
            if matches:
                self.goto_url = matches.group("url")
                continue

            matches = re.search(
                r"(?P<url>https://[a-z0-9-]+\.webex\.com/meet/[a-z0-9_.-]+)", line
            )
            if matches:
                self.webex_url = matches.group("url")
                continue

        try:
            events[self.event_name] = self._save()
        except RuntimeError:
            pass

        if len(events) == 0:
            wf.warn_empty("No more joinable events were found")
        else:
            sorted_events = OrderedDict(
                sorted(events.items(), key=lambda t: t[1].sort_time)
            )
            for key in sorted_events.keys():
                event = events[key]
                wf.add_item(
                    "{}".format(event.event_name),
                    event.description(),
                    arg=event.url(),
                    valid=True,
                    icon=event.icon(),
                )
        self.events = events
        wf.send_feedback()


if __name__ == "__main__":
    wf = Workflow3()
    cs = CalendarScanner()
    cs.input_filename = os.environ.get("NEXT_CHIME_FILENAME", None)  # Allow debugging
    sys.exit(wf.run(cs.get_events))
