def make_quest(
	quest_id,
	properties="",
	objectives="",
	rewards=""
):
	quest = f"<quest id=\"{quest_id}\">\n"
	quest += f"{properties}{objectives}{rewards}"
	quest += "\n</quest>\n"
	return (quest_id, quest)

class QuestList(list):
	def write(self):
		with open("quests.xml", "w") as file:
			file.write("")
		with open("quests.xml", "a") as file:
			for i in self:
				file.write(i[1])
		with open("quest_ids.txt", "w") as file:
			file.write("")
		with open("quest_ids.txt", "a") as file:
			for i in self:
				file.write(i[0])
				file.write("\n")
