using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// The mod's particle effects (from its bundle) and the game's own, played by the traps' PlayFx on every game that
/// draws them. Buffs can only attach the game's own particle effects, so effects on zombies (water dripping off soaked
/// ones, tar, frost) are attached from here, for as long as the status lasts; attaching one again extends it.
/// </summary>
public static class FxDEM
{
    private const string Bundle = "#@modfolder(TrapsExpanded):Resources/trapsexpanded.unity3d?";

    private static readonly Dictionary<string, GameObject> templates = new Dictionary<string, GameObject>();
    private static readonly HashSet<string> failed = new HashSet<string>();
    private static readonly Dictionary<string, FxLifetimeDEM> attached = new Dictionary<string, FxLifetimeDEM>();

    /// <summary>One of the mod's effect prefabs (null if it isn't in the bundle).</summary>
    public static GameObject Template(string name)
    {
        if (templates.TryGetValue(name, out GameObject t) && t != null)
        {
            return t;
        }
        if (failed.Contains(name))
        {
            return null;
        }
        t = DataLoader.LoadAsset<GameObject>(Bundle + name);
        if (t == null)
        {
            failed.Add(name);
            Debug.LogWarning("[TrapsExpanded] Couldn't load the " + name + " effect from the bundle");
            return null;
        }
        templates[name] = t;
        return t;
    }

    /// <summary>Attaches a looping effect to an entity at `height` of its eye height for `seconds`.</summary>
    public static void Attach(EntityAlive entity, string name, float seconds, float height = 0.7f)
    {
        if (entity == null || GameManager.IsDedicatedServer)
        {
            return;
        }
        string key = entity.entityId + ":" + name;
        if (attached.TryGetValue(key, out FxLifetimeDEM fx) && fx != null && fx.Running)
        {
            fx.Until = Mathf.Max(fx.Until, Time.time + seconds);
            return;
        }
        GameObject prefab = Template(name);
        if (prefab == null)
        {
            return;
        }
        if (attached.Count > 128)
        {
            Prune();
        }
        GameObject go = Object.Instantiate(prefab, entity.transform, false);
        go.transform.localPosition = new Vector3(0f, entity.GetEyeHeight() * height, 0f);
        go.SetActive(true);
        fx = go.AddComponent<FxLifetimeDEM>();
        fx.Until = Time.time + seconds;
        attached[key] = fx;
    }

    private static void Prune()
    {
        List<string> done = new List<string>();
        foreach (KeyValuePair<string, FxLifetimeDEM> kv in attached)
        {
            if (kv.Value == null || !kv.Value.Running)
            {
                done.Add(kv.Key);
            }
        }
        foreach (string key in done)
        {
            attached.Remove(key);
        }
    }

    /// <summary>Plays one of the mod's effects at a world position for `seconds` (looping ones stop emitting then).
    /// Returns it so a trap can move it (a flying glob).</summary>
    public static GameObject Spawn(string name, Vector3 worldPos, Quaternion rotation, float seconds,
        Transform parent = null)
    {
        if (GameManager.IsDedicatedServer)
        {
            return null;
        }
        GameObject prefab = Template(name);
        if (prefab == null)
        {
            return null;
        }
        GameObject go = Object.Instantiate(prefab, worldPos - Origin.position, rotation);
        if (parent != null)
        {
            go.transform.SetParent(parent, true);
        }
        go.SetActive(true);
        FxLifetimeDEM fx = go.AddComponent<FxLifetimeDEM>();
        fx.Until = Time.time + seconds;
        return go;
    }

    /// <summary>Plays one of the game's own particle effects (ParticleEffects/&lt;name&gt;) at a world position,
    /// removed after `seconds` (0 leaves it to the effect). Returns its transform.</summary>
    public static Transform Vanilla(string name, Vector3 worldPos, Quaternion rotation, float seconds,
        Transform parent = null)
    {
        // The game files its particle effects without their prefabs' p_ (p_burning_barrel is "burning_barrel")
        if (name != null && name.StartsWith("p_"))
        {
            name = name.Substring(2);
        }
        if (GameManager.IsDedicatedServer || !ParticleEffect.IsAvailable(name))
        {
            return null;
        }
        Transform t = GameManager.Instance.SpawnParticleEffectClientForceCreation(
            new ParticleEffect(name, worldPos, rotation, 1f, Color.white), -1, true);
        if (t == null)
        {
            return null;
        }
        if (parent != null)
        {
            t.SetParent(parent, true);
        }
        if (seconds > 0f)
        {
            FxLifetimeDEM fx = t.gameObject.AddComponent<FxLifetimeDEM>();
            fx.Until = Time.time + seconds;
        }
        return t;
    }
}

/// <summary>Water dripping off soaked zombies (the Sprinkler's).</summary>
public static class DripFxDEM
{
    public static void Attach(EntityAlive entity, float seconds)
    {
        FxDEM.Attach(entity, "SoakDrip", seconds);
    }
}

/// <summary>Stops a looping effect's emission at Until and removes it once its particles are gone.</summary>
public class FxLifetimeDEM : MonoBehaviour
{
    public float Until;

    public bool Running => enabled;

    private void Update()
    {
        if (Time.time < Until)
        {
            return;
        }
        foreach (ParticleSystem ps in GetComponentsInChildren<ParticleSystem>())
        {
            ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }
        foreach (Light l in GetComponentsInChildren<Light>())
        {
            l.enabled = false;
        }
        Destroy(gameObject, 1.5f);
        enabled = false;
    }
}
