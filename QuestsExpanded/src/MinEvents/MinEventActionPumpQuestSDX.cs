﻿using System.Xml;
using System.Xml.Linq;

public class MinEventActionPumpQuestSDX : MinEventActionRemoveBuff
{
    // This loops through all the targets, refreshing the quest. 
    //  <triggered_effect trigger="onSelfBuffStart" action="PumpQuestSDX, SCore" target="self"  />
    public override void Execute(MinEventParams _params)
    {
        for (var j = 0; j < targets.Count; j++)
        {
            var entityPlayer = targets[j] as EntityPlayerLocal;
            if (entityPlayer != null)
                for (var k = 0; k < entityPlayer.QuestJournal.quests.Count; k++)
                    for (var l = 0; l < entityPlayer.QuestJournal.quests[k].Objectives.Count; l++)
                        entityPlayer.QuestJournal.quests[k].Objectives[l].Refresh();
        }
    }
}
