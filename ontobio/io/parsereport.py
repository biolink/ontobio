import json

import typing
from typing import Dict, List, Optional

Message = Dict[str, str]

class Report(object):

    def __init__(self, group, dataset):
        self.group = group
        self.dataset = dataset
        self.messages = {} # type: Dict[str, List[Message]] # rule id --> List of messages
        self.messages["other"] = []
        self._rule_message_cap = 10000

    def _rule_id(self, id: int) -> str:
        """
        Convert an integer into a gorule key id.
        """
        if id is None or id == 0 or id >= 10000000:
            return "other"

        return "gorule-{:0>7}".format(id)

    def message(self, message: Message, rule: Optional[int]) -> None:
        """
        Add a message to the appropriate list of messages. If `rule` refers
        to a valid id range for a go rule, the message is entered in a list
        keyed by the full gorule-{id}. Otherwise, if `rule` is None, or
        outside the id range, then we put this in the catch-all "other"
        keyed list of messages.
        """
        rule_id = self._rule_id(rule)
        if rule_id not in self.messages:
            self.messages[rule_id] = []

        if len(self.messages[rule_id]) < self._rule_message_cap:
            self.messages[rule_id].append(message)

    def json(self, lines, associations, skipped) -> Dict:
        result = {
            "group": self.group,
            "dataset": self.dataset,
            "lines": lines,
            "skipped_lines": skipped,
            "associations": associations,
            "messages": self.messages
        }
        return result
