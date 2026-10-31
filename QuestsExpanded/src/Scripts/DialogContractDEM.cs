/*
 * Trader dialog options for contracts (Config/dialogs.xml), run on the client of the player talking to the trader.
 * 	<action type="ContractDEM, QuestsExpanded" id="start"/>                start a contract
 * 	<action type="ContractDEM, QuestsExpanded" id="status"/>               show where the contract stands
 * 	<action type="ContractDEM, QuestsExpanded" id="pick" value="deadeye"/> take a boon from the trader's offer
 * 	<action type="ContractDEM, QuestsExpanded" id="cashout"/>              collect the pot and end the contract
 */
public class DialogActionContractDEM : BaseDialogAction
{
    public override void PerformAction(EntityPlayer player)
    {
        switch (ID)
        {
            case "start":
                ContractsDEM.Send(NetPackageContractDEM.Ops.Start);
                break;
            case "status":
                ContractsDEM.ShowStatus();
                break;
            case "pick":
                ContractsDEM.Send(NetPackageContractDEM.Ops.Pick, text: Value);
                break;
            case "cashout":
                ContractsDEM.Send(NetPackageContractDEM.Ops.CashOut);
                break;
        }
    }
}

/*
 * Shows a contract dialog option only when it applies.
 * 	<requirement type="ContractDEM, QuestsExpanded" id="none" requirementtype="Hide"/>                    no contract running
 * 	<requirement type="ContractDEM, QuestsExpanded" id="active" requirementtype="Hide"/>                  a contract is running
 * 	<requirement type="ContractDEM, QuestsExpanded" id="cashout" requirementtype="Hide"/>                 at least one stage done
 * 	<requirement type="ContractDEM, QuestsExpanded" id="offer" requirementtype="Hide"/>                   there's a boon to pick
 * 	<requirement type="ContractDEM, QuestsExpanded" id="offered" value="deadeye" requirementtype="Hide"/> this boon is on offer
 */
public class DialogRequirementContractDEM : BaseDialogRequirement
{
    public override bool CheckRequirement(EntityPlayer player, EntityNPC talkingTo)
    {
        ContractStateDEM contract = ContractsDEM.Mine;
        bool active = ContractsDEM.Active;
        switch (ID)
        {
            case "none":
                return ContractsDEM.Synced && !contract.Active;
            case "active":
                return active;
            case "cashout":
                return active && contract.Stage >= 1;
            case "offer":
                return active && contract.Offer.Count > 0;
            case "offered":
                return active && contract.Offer.Contains(Value);
            default:
                return false;
        }
    }
}
