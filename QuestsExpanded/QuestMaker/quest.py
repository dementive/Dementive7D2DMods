class Quest:
	"""7D2D Quest Template class"""

	def __init__(
		self,
		quest_id,
		properties="",
		objectives="",
		rewards="",
	):
		self.quest = f"<quest id=\"{quest_id}\">\n"
		self.quest += f"{properties}{objectives}{rewards}"
		self.quest += "\n</quest>"
