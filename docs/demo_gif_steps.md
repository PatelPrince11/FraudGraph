# FraudGraph — Demo Video & Final Repo Steps

## 1. Demo Video — Server Later

The server step will reuse the exact Docker Compose setup you just ran, so none of this work gets thrown away.

---

## 2. Before Recording

### Start the Stack

Make sure the stack is running:

```bash
docker compose ps
```

All three services should show as **up/running**.

### Open FraudGraph

Open this address in your browser:

```text
http://localhost:8080/#16bf2e46c54369a8eab2214649506425
```

This is the ring case from earlier and the best story in the data.

### Browser Setup

- Make the browser window about the size of a laptop screen.
- Close all other tabs.
- Hide the bookmarks bar.
- Set browser zoom to **100%** with `Cmd+0`.
- Click the graph once and wait for it to settle so it does not move while recording.

---

## 3. What to Record

**Target length: ~60 seconds**

**No narration.**

Move the mouse slowly. Viewers should have about **2 seconds** on anything you point at.

| Time | Action | What It Shows |
|---|---|---|
| **0–4s** | Hold still on the full dashboard | The whole tool at a glance |
| **4–12s** | Hover over **"Spend in past 24h = $1,935"** in the reasons section | A **$24.84 charge** got flagged because of what happened before it |
| **12–20s** | Move to the history table and hover over the **$1,063** and **$834** charges | The fraud burst that happened the day before |
| **20–32s** | In the graph, click the blue device square shared by the most cards, then click one of the red cards linked to it | Other cards used the same device, and they have alerts too |
| **32–42s** | Click **Follow all**, hold for 3 seconds, then click **Follow flagged links** again | The noise that the default mode filters out |
| **42–52s** | Tick **Show ground truth** | Fraud labels appear, plus the amber ring on the card the model missed |
| **52–60s** | Click 2 other alerts in the queue on the left | The tool works for any alert, not only this one |

---

## 4. Practice Run

Do **one complete practice run** before recording the final video.

---

## 5. Record the Video

Press:

```text
Cmd+Shift+5
```

Choose:

**Record Selected Portion**

Drag the recording box over the **browser's page area only**.

Do **not** include:

- Browser tabs
- Address bar
- Other desktop content

Then click **Record**.

To stop recording, click the **stop button in the menu bar**.

The `.mov` file should appear on your Desktop.

---

## 6. Convert the Recording to GIF

Make sure `ffmpeg` is installed.

If you do not have it:

```bash
brew install ffmpeg
```

From the `fraudgraph/` directory, run:

```bash
mkdir -p docs

ffmpeg -i ~/Desktop/"Screen Recording"*.mov \
  -vf "fps=10,scale=1100:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer" \
  -loop 0 docs/demo.gif

ls -lh docs/demo.gif
```

### GIF Settings

The `-vf` setting:

- Uses **10 frames per second**
- Scales the GIF to **1100 pixels wide**
- Uses Lanczos scaling
- Creates a custom **128-color palette**
- Applies dithering for a sharper result

Keep the GIF **under 10 MB** so GitHub displays it properly.

If the GIF is too large, change:

```text
scale=1100
```

to:

```text
scale=900
```

You can also record a shorter demo.

### If You Have Multiple Screen Recordings

If there is more than one screen recording on your Desktop, replace:

```text
~/Desktop/"Screen Recording"*.mov
```

with the exact filename.

---

## 7. Update README

In `README.md`, replace:

```markdown
![Dashboard](docs/dashboard.png)
```

with:

```markdown
![FraudGraph demo](docs/demo.gif)
```

---

## 8. Fix CI

Pin CI to **Ubuntu 24.04** so GitHub's October runner upgrade does not unexpectedly break the project.

On a Mac, `sed -i` requires the empty `''` argument.

Run:

```bash
sed -i '' 's/ubuntu-latest/ubuntu-24.04/' .github/workflows/ci.yml
```

---

## 9. Commit and Push

Run:

```bash
git add .
git commit -m "Demo GIF, pin CI runner"
git push
```

---

## 10. Final GitHub Check

Open the repository page on GitHub.

Check that:

- [ ] The README loads correctly.
- [ ] The FraudGraph demo GIF appears near the top.
- [ ] The GIF plays correctly.
- [ ] The GIF is under 10 MB.
- [ ] CI is using Ubuntu 24.04.
- [ ] The latest commit is pushed successfully.

---

## 11. Make the Repository Public

On GitHub:

**Settings → General → Danger Zone**

Then make the repository **public**.

---

## 12. Final Step

Send the public repository link.

The review will focus on:

- What is visible in the first 30 seconds
- Whether the project immediately communicates its purpose
- README quality
- Demo quality
- Technical credibility
- Project structure
- Resume/recruiter impact
- What should be fixed before using it in applications