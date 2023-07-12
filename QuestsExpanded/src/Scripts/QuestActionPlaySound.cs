// <action type="QuestActionPlaySoundDEM" value="Sounds/Step/crawlerstepcloth1"/>

public class QuestActionPlaySoundDEM : QuestActionShowTip
{
    public override void SetupAction()
    {
    }

    public override void PerformAction(Quest action)
    {
        EntityAlive myEntity = null;
        if (OwnerQuest.OwnerJournal.OwnerPlayer != null)
            myEntity = OwnerQuest.OwnerJournal.OwnerPlayer;

        myEntity?.PlayOneShot(Value, true);
    }

    public override BaseQuestAction Clone()
    {
        var questActionPlaySound = new QuestActionPlaySoundDEM();
        CopyValues(questActionPlaySound);
        return questActionPlaySound;
    }
}