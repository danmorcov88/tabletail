# Recording the demo GIF

The GIF at the top of the README (`docs/demo.gif`) shows `tabletail tail`
reacting to a live stream of changes. Here is how to reproduce it.

## 1. Start the demo database

```bash
docker compose -f examples/docker-compose.yml up -d
export DATABASE_URL=postgres://demo:demo@localhost:5433/demo
```

## 2. Record with asciinema + agg (recommended)

[asciinema](https://asciinema.org/) records the terminal; [agg](https://github.com/asciinema/agg)
converts the recording to a GIF.

```bash
# Terminal you record: start the recorder, then run tabletail.
asciinema rec demo.cast --command "tabletail tail --table orders --interval 1"

# In a second terminal, drive the changes:
bash examples/demo.sh

# Back in the first terminal, press Ctrl-C to stop tabletail, then exit the
# recording. Convert to a GIF:
agg --theme monokai --font-size 22 demo.cast docs/demo.gif
```

## 3. Or record with terminalizer

```bash
terminalizer record demo            # run `tabletail tail ...`, drive demo.sh, then exit
terminalizer render demo -o docs/demo.gif
```

## Tips for a clean recording

- Keep the window around 100×24 so the GIF stays legible when scaled down.
- `--interval 1` makes the stream feel responsive without flooding.
- Run `examples/demo.sh` once; it resets the table and plays a ~12 second script.
