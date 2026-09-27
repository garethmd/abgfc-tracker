"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Pencil, Play, Plus, Trash2, TvMinimalPlay } from "lucide-react";
import { toast } from "sonner";
import { $api, errorMessage, type Schema } from "@/lib/api/client";
import { SectionTitle } from "@/components/page-header";
import { Card } from "@/components/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Field } from "@/components/features/fixtures/fixture-form";

type Video = Schema["FixtureVideoRead"];

/** Match videos posted to YouTube, watched next to the stats. */
export function FixtureVideos({ fixtureId, canEdit }: { fixtureId: number; canEdit: boolean }) {
  const qc = useQueryClient();
  const path = { params: { path: { fixture_id: fixtureId } } };
  const videos = $api.useQuery("get", "/api/v1/fixtures/{fixture_id}/media", path);
  const create = $api.useMutation("post", "/api/v1/fixtures/{fixture_id}/media");
  const update = $api.useMutation("patch", "/api/v1/fixtures/{fixture_id}/media/{media_id}");
  const remove = $api.useMutation("delete", "/api/v1/fixtures/{fixture_id}/media/{media_id}");
  const [editing, setEditing] = useState<Video | "new" | null>(null);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/fixtures/{fixture_id}/media"] });

  function open(v: Video | "new") {
    setEditing(v);
    setUrl(v === "new" ? "" : v.url);
    setTitle(v === "new" ? "" : (v.title ?? ""));
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editing === "new") {
        await create.mutateAsync({ ...path, body: { url: url.trim(), title: title.trim() || null } });
      } else if (editing) {
        await update.mutateAsync({
          params: { path: { fixture_id: fixtureId, media_id: editing.id } },
          body: { url: url.trim(), title: title.trim() || null },
        });
      }
      invalidate();
      setEditing(null);
      toast.success(editing === "new" ? "Video added" : "Video updated");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  async function onDelete(v: Video) {
    try {
      await remove.mutateAsync({ params: { path: { fixture_id: fixtureId, media_id: v.id } } });
      invalidate();
      setEditing(null);
      toast.success("Video removed");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const list = videos.data ?? [];
  if (!list.length && !canEdit) return null;

  return (
    <section className="mt-8">
      <div className="mb-3 flex items-baseline justify-between">
        <SectionTitle className="mb-0">Video</SectionTitle>
        {canEdit && list.length > 0 && (
          <button type="button" className="text-xs font-medium text-primary" onClick={() => open("new")}>
            Add
          </button>
        )}
      </div>

      {list.length > 0 ? (
        <div className="space-y-3">
          {list.map((v) => (
            <VideoCard key={v.id} video={v} canEdit={canEdit} onEdit={() => open(v)} />
          ))}
        </div>
      ) : (
        canEdit && (
          <Card className="flex flex-col items-center gap-3 p-6 text-center">
            <TvMinimalPlay className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Paste the YouTube link and the match plays here, next to the stats.
            </p>
            <Button variant="outline" className="h-11" onClick={() => open("new")}>
              <Plus className="size-4" /> Add video
            </Button>
          </Card>
        )
      )}

      <Sheet open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <SheetContent side="bottom" className="max-h-[85dvh] overflow-y-auto rounded-t-2xl pb-[calc(env(safe-area-inset-bottom)+1rem)]">
          <SheetHeader className="text-left">
            <SheetTitle>{editing === "new" ? "Add video" : "Edit video"}</SheetTitle>
          </SheetHeader>
          <form onSubmit={onSave} className="space-y-4 px-4">
            <Field label="YouTube link">
              <Input
                className="h-11"
                inputMode="url"
                autoCapitalize="off"
                autoCorrect="off"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://youtu.be/…"
                required
                autoFocus
              />
            </Field>
            <Field label="Title">
              <Input className="h-11" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Match video" />
              <p className="text-xs text-muted-foreground">
                Optional - useful when there&apos;s more than one, e.g. &ldquo;Second half&rdquo;.
              </p>
            </Field>
            <Button type="submit" className="h-12 w-full" disabled={create.isPending || update.isPending}>
              {editing === "new" ? "Add" : "Save"}
            </Button>
            {editing !== "new" && editing && (
              <Button type="button" variant="ghost" className="h-11 w-full text-destructive" onClick={() => onDelete(editing)}>
                <Trash2 className="size-4" /> Remove video
              </Button>
            )}
          </form>
        </SheetContent>
      </Sheet>
    </section>
  );
}

/**
 * Click to play: nothing is requested from YouTube until someone taps, and then the
 * player is the nocookie one. Keeps a page about children off Google until it's asked for.
 */
function VideoCard({ video, canEdit, onEdit }: { video: Video; canEdit: boolean; onEdit: () => void }) {
  const [playing, setPlaying] = useState(false);
  return (
    <Card className="overflow-hidden">
      {playing ? (
        <div className="aspect-video w-full bg-black">
          <iframe
            src={`https://www.youtube-nocookie.com/embed/${video.video_id}?autoplay=1&rel=0`}
            title={video.title ?? "Match video"}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            className="size-full border-0"
          />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setPlaying(true)}
          className="flex aspect-video w-full flex-col items-center justify-center gap-3 bg-muted/60 transition-colors hover:bg-muted"
          aria-label={`Play ${video.title ?? "match video"}`}
        >
          <span className="flex size-14 items-center justify-center rounded-full bg-background/90 shadow-sm ring-1 ring-border">
            <Play className="ml-0.5 size-6 fill-current" />
          </span>
          <span className="text-sm font-medium">{video.title ?? "Match video"}</span>
        </button>
      )}
      <div className="flex items-center gap-2 px-3 py-2">
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{video.title ?? "Match video"}</span>
        <a
          href={video.url}
          target="_blank"
          rel="noreferrer"
          className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label="Open on YouTube"
        >
          <ExternalLink className="size-4" />
        </a>
        {canEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="flex size-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground"
            aria-label="Edit video"
          >
            <Pencil className="size-4" />
          </button>
        )}
      </div>
    </Card>
  );
}
