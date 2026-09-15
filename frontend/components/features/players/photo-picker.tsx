"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Camera, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { errorMessage, fetchClient, type Schema } from "@/lib/api/client";
import { PlayerAvatar } from "@/components/player-avatar";
import { Button } from "@/components/ui/button";

/** Upload / replace / remove a player's profile photo. Coaches only (the API enforces). */
export function PhotoPicker({ player, onChanged }: { player: Schema["PlayerRead"]; onChanged?: () => void }) {
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/players"] });
    qc.invalidateQueries({ queryKey: ["get", "/api/v1/team-seasons"] });
    onChanged?.();
  };

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    const body = new FormData();
    body.append("file", file);
    const { error } = await fetchClient.PUT("/api/v1/players/{player_id}/photo", {
      params: { path: { player_id: player.id } },
      // openapi-fetch would JSON-encode; hand it the FormData untouched
      body: body as unknown as { file: string },
      bodySerializer: (b) => b as unknown as BodyInit,
    });
    setBusy(false);
    if (error) return toast.error(errorMessage(error, "Couldn't upload that photo"));
    toast.success("Photo updated");
    invalidate();
  }

  async function onRemove() {
    if (!confirm("Remove this photo?")) return;
    setBusy(true);
    const { error } = await fetchClient.DELETE("/api/v1/players/{player_id}/photo", { params: { path: { player_id: player.id } } });
    setBusy(false);
    if (error) return toast.error(errorMessage(error));
    invalidate();
  }

  return (
    <div className="flex items-center gap-4">
      <PlayerAvatar playerId={player.id} name={player.display_name} photoKey={player.photo_key} size={72} />
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => input.current?.click()}>
          <Camera className="size-4" /> {player.photo_key ? "Change photo" : "Add photo"}
        </Button>
        {player.photo_key && (
          <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={onRemove}>
            <Trash2 className="size-4" /> Remove
          </Button>
        )}
        <input ref={input} type="file" accept="image/*" className="hidden" onChange={onFile} />
      </div>
    </div>
  );
}
