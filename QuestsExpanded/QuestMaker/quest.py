def make_quest(
	quest_id,
	properties="",
	objectives="",
	rewards=""
):
	quest = f"<quest id=\"{quest_id}\">\n"
	quest += f"{properties}{objectives}{rewards}"
	quest += "\n</quest>\n"
	return quest

class QuestList(list):
	def write(self):
		with open("quests.xml", "w") as file:
			file.write("")
		with open("quests.xml", "a") as file:
			for i in self:
				file.write(i)
