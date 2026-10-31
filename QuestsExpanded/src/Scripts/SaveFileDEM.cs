using System;
using System.IO;

/// <summary>
/// A file QuestsExpanded keeps in the current world's save folder on the server (QuestsExpanded/&lt;name&gt;), for
/// state that has to outlast logouts and restarts and that no single player owns.
/// </summary>
public class SaveFileDEM
{
    private readonly string name;
    private string loadedFrom;

    public SaveFileDEM(string name)
    {
        this.name = name;
    }

    private static string Folder()
    {
        try
        {
            return Path.Combine(GameIO.GetSaveGameDir(), "QuestsExpanded");
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// True when the world changed since the last load (or nothing was loaded yet), so the caller should reload.
    /// </summary>
    public bool NeedsLoad()
    {
        return Folder() != loadedFrom;
    }

    /// <summary>
    /// Reads the file for the current world with <paramref name="read"/>, if there is one.
    /// </summary>
    public void Load(Action<PooledBinaryReader> read)
    {
        string folder = Folder();
        loadedFrom = folder;
        if (folder == null)
            return;
        string path = Path.Combine(folder, name);
        if (!File.Exists(path))
            return;
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
            Log.Warning($"QuestsExpanded: couldn't read {path}: {e.Message}");
        }
    }

    public void Save(Action<PooledBinaryWriter> write)
    {
        string folder = Folder();
        if (folder == null)
            return;
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
                File.Delete(path);
            File.Move(temp, path);
        }
        catch (Exception e)
        {
            Log.Warning($"QuestsExpanded: couldn't save {name}: {e.Message}");
        }
    }
}
