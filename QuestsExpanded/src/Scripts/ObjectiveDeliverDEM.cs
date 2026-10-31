/*
 * Delivery objective for commissions: like Fetch, the items are taken from the player when the quest is turned in.
 * In a party, only the player who took the commission from the trader delivers the items; on the copies shared
 * with the rest of the party the objective is already complete, so everyone can turn in for their own reward.
 * 	<objective type="DeliverDEM, QuestsExpanded" id="resourceForgedIron" value="20" phase="2"/>
 */
public class ObjectiveDeliverDEM : ObjectiveFetch
{
    private bool IsSharedCopy => OwnerQuest != null && OwnerQuest.SharedOwnerID != -1;

    public override void Refresh()
    {
        if (!IsSharedCopy)
        {
            base.Refresh();
            return;
        }

        if (Complete)
            return;

        currentCount = itemCount;
        CurrentValue = (byte)itemCount;
        SetupDisplay();
        Complete = OwnerQuest.CheckRequirements();
        if (Complete)
            OwnerQuest.RefreshQuestCompletion();
    }

    public override void RemoveObjectives()
    {
        if (!IsSharedCopy)
            base.RemoveObjectives();
    }

    public override BaseObjective Clone()
    {
        var objective = new ObjectiveDeliverDEM();
        CopyValues(objective);
        objective.KeepItems = KeepItems;
        return objective;
    }
}
