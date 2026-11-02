using System.Collections.Generic;
using System.Text;
using UnityEngine;

/// <summary>
/// The `ze debug` readout: above every zombie within 30 m, its profile and, where its AI runs (single player and the
/// host), the AI tasks it's running right now. For tuning only; off by default.
/// </summary>
public class ZedDebug : MonoBehaviour
{
    private static ZedDebug instance;
    private GUIStyle style;

    public static bool Toggle()
    {
        if (instance != null)
        {
            Destroy(instance.gameObject);
            instance = null;
            return false;
        }
        GameObject go = new GameObject("ZedDebug");
        DontDestroyOnLoad(go);
        instance = go.AddComponent<ZedDebug>();
        return true;
    }

    /// <summary>The AI tasks a zombie is running (only where its AI runs).</summary>
    public static string Tasks(EntityAlive e)
    {
        if (e.aiManager == null)
        {
            return "AI runs on the server";
        }
        StringBuilder sb = new StringBuilder();
        Append(sb, e.aiManager.targetTasks);
        Append(sb, e.aiManager.tasks);
        return sb.Length > 0 ? sb.ToString() : "idle";
    }

    private static void Append(StringBuilder sb, EAITaskList list)
    {
        List<EAITaskEntry> running = list?.GetExecutingTasks();
        if (running == null)
        {
            return;
        }
        foreach (EAITaskEntry t in running)
        {
            if (sb.Length > 0)
            {
                sb.Append(", ");
            }
            sb.Append(t.action.GetType().Name.Replace("EAI", ""));
        }
    }

    private void OnGUI()
    {
        World world = GameManager.Instance?.World;
        Camera cam = Camera.main;
        if (world == null || cam == null)
        {
            return;
        }
        if (style == null)
        {
            style = new GUIStyle(GUI.skin.label) { fontSize = 12, alignment = TextAnchor.LowerCenter };
            style.normal.textColor = new Color(1f, 0.95f, 0.6f);
        }
        foreach (EntityAlive e in world.EntityAlives)
        {
            if (!ZedStore.IsZombie(e) || e.IsDead())
            {
                continue;
            }
            Vector3 head = e.getHeadPosition() - Origin.position + Vector3.up * 0.5f;
            Vector3 screen = cam.WorldToScreenPoint(head);
            if (screen.z <= 0f || screen.z > 30f)
            {
                continue;
            }
            ZedProfile p = ZedStore.Get(e.entityId);
            string text = e.EntityClass.entityClassName + " #" + e.entityId + "\n" + (p != null ? p.ToString() : "no profile")
                + "\n" + Tasks(e);
            Rect r = new Rect(screen.x - 220f, Screen.height - screen.y - 60f, 440f, 60f);
            GUI.Label(new Rect(r.x + 1, r.y + 1, r.width, r.height), text, Shadow());
            GUI.Label(r, text, style);
        }
    }

    private GUIStyle shadow;

    private GUIStyle Shadow()
    {
        if (shadow == null)
        {
            shadow = new GUIStyle(style);
            shadow.normal.textColor = Color.black;
        }
        return shadow;
    }
}
