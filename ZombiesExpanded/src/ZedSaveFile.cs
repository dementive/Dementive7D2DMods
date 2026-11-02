using System;
using System.IO;

/// <summary>
/// A file Zombies Expanded keeps in the current world's save folder on the server (ZombiesExpanded/&lt;name&gt;): the
/// profiles of the zombies the game saves.
/// </summary>
public class ZedSaveFile
{
    private readonly string name;
    private string loadedFrom;

    public ZedSaveFile(string name)
    {
        this.name = name;
    }

    private static string Folder()
    {
        try
        {
            return Path.Combine(GameIO.GetSaveGameDir(), "ZombiesExpanded");
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>Forgets which world was loaded (leaving a world), so the next one, even the same again, is read.</summary>
    public void Reset()
    {
        loadedFrom = null;
    }

    /// <summary>True when the world changed since the last load (or nothing was loaded yet).</summary>
    public bool NeedsLoad()
    {
        return Folder() != loadedFrom;
    }

    public void Load(Action<PooledBinaryReader> read)
    {
        string folder = Folder();
        loadedFrom = folder;
        if (folder == null)
        {
            return;
        }
        string path = Path.Combine(folder, name);
        if (!File.Exists(path))
        {
            return;
        }
        try
        {
            using (FileStream stream = File.OpenRead(path))
            {
                var reader = new PooledBinaryReader();
                reader.SetBaseStream(stream);
                read(reader);
            }
        }
        catch (Exception e)
        {
            Log.Warning($"[ZombiesExpanded] Couldn't read {path}: {e.Message}");
        }
    }

    public void Save(Action<PooledBinaryWriter> write)
    {
        string folder = Folder();
        if (folder == null)
        {
            return;
        }
        try
        {
            Directory.CreateDirectory(folder);
            string path = Path.Combine(folder, name);
            string temp = path + ".tmp";
            using (FileStream stream = File.Create(temp))
            {
                var writer = new PooledBinaryWriter();
                writer.SetBaseStream(stream);
                write(writer);
                writer.Flush();
            }
            if (File.Exists(path))
            {
                File.Delete(path);
            }
            File.Move(temp, path);
        }
        catch (Exception e)
        {
            Log.Warning($"[ZombiesExpanded] Couldn't save {name}: {e.Message}");
        }
    }
}
