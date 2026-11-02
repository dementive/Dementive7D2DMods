using UnityEngine;

/// <summary>
/// Client: something a trap fires (an arrow, a rebar bolt, a tar glob) flying from the trap to where it hit, pointing
/// along its path, with an optional arc. The hit itself is already done on the server; at the end it plays its impact
/// effect and either sticks there for a while or disappears.
/// </summary>
public class ProjectileFxDEM : MonoBehaviour
{
    private Vector3 from;
    private Vector3 to;
    private float duration;
    private float arc;
    private float age;
    private string impactFx;
    private float stickSeconds;
    private bool landed;

    /// <summary>Launches the mod's effect prefab `prefab` between two world positions at `speed` m/s.</summary>
    public static ProjectileFxDEM Launch(string prefab, Vector3 fromWorld, Vector3 toWorld, float speed, float arcHeight,
        string impact, float stick)
    {
        if (GameManager.IsDedicatedServer)
        {
            return null;
        }
        GameObject template = FxDEM.Template(prefab);
        if (template == null)
        {
            return null;
        }
        GameObject go = Instantiate(template, fromWorld - Origin.position,
            Quaternion.LookRotation((toWorld - fromWorld).sqrMagnitude > 0.0001f ? toWorld - fromWorld : Vector3.forward));
        go.SetActive(true);
        ProjectileFxDEM p = go.AddComponent<ProjectileFxDEM>();
        p.from = fromWorld;
        p.to = toWorld;
        p.duration = Mathf.Max(0.05f, Vector3.Distance(fromWorld, toWorld) / Mathf.Max(1f, speed));
        p.arc = arcHeight;
        p.impactFx = impact;
        p.stickSeconds = stick;
        return p;
    }

    private Vector3 At(float k)
    {
        return Vector3.Lerp(from, to, k) + Vector3.up * (arc * 4f * k * (1f - k));
    }

    private void Update()
    {
        age += Time.deltaTime;
        if (landed)
        {
            if (age >= stickSeconds)
            {
                Destroy(gameObject);
            }
            return;
        }
        float k = Mathf.Clamp01(age / duration);
        Vector3 pos = At(k);
        Vector3 ahead = At(Mathf.Min(1f, k + 0.02f)) - pos;
        transform.position = pos - Origin.position;
        if (ahead.sqrMagnitude > 0.000001f)
        {
            transform.rotation = Quaternion.LookRotation(ahead);
        }
        if (k < 1f)
        {
            return;
        }
        landed = true;
        age = 0f;
        if (!string.IsNullOrEmpty(impactFx))
        {
            FxDEM.Spawn(impactFx, to, Quaternion.identity, 0.4f);
        }
        if (stickSeconds <= 0f)
        {
            Destroy(gameObject);
            return;
        }
        // Stop trails and particles but leave the shaft stuck where it hit
        foreach (TrailRenderer trail in GetComponentsInChildren<TrailRenderer>())
        {
            trail.emitting = false;
        }
        foreach (ParticleSystem ps in GetComponentsInChildren<ParticleSystem>())
        {
            ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }
    }
}
