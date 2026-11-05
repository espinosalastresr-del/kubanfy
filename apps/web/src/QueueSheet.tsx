import { QueueTrackMeta, trackArtistsLabel } from "./queue";

type Props = {
  queueIds: string[];
  activeTrackId: string | null;
  isPlaying: boolean;
  queueMeta: Record<string, QueueTrackMeta>;
  activeTrack: any;
  onPlay: (id: string) => void;
  onRemove: (id: string) => void;
  onClearKeepCurrent: () => void;
  onClose: () => void;
};

export function QueueSheet({
  queueIds,
  activeTrackId,
  isPlaying,
  queueMeta,
  activeTrack,
  onPlay,
  onRemove,
  onClearKeepCurrent,
  onClose,
}: Props) {
  return (
    <div className="queue-sheet glass" role="dialog" aria-label="Cola de reproducción">
      <div className="queue-sheet-head">
        <div>
          <strong>Cola</strong>
          <span>{queueIds.length} {queueIds.length === 1 ? "canción" : "canciones"}</span>
        </div>
        <div className="queue-sheet-actions">
          <button type="button" className="tiny-action queue-clear" onClick={onClearKeepCurrent} disabled={queueIds.length <= 1}>
            Dejar solo actual
          </button>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar cola">×</button>
        </div>
      </div>
      <ol className="queue-list">
        {queueIds.map((qid, index) => {
          const meta = queueMeta[qid];
          const isCurrent = qid === activeTrackId;
          return (
            <li key={`${qid}-${index}`} className={`queue-item${isCurrent ? " is-current" : ""}`}>
              <button type="button" className="queue-item-main" onClick={() => onPlay(qid)} aria-current={isCurrent ? "true" : undefined}>
                <span className="queue-index">{isCurrent && isPlaying ? "▶" : index + 1}</span>
                <span className="queue-item-meta">
                  <strong>{meta?.title || (isCurrent ? activeTrack?.title : null) || "Canción"}</strong>
                  <small>{meta?.artists || (isCurrent ? trackArtistsLabel(activeTrack) : "KubanFy")}</small>
                </span>
              </button>
              <button type="button" className="icon-button queue-remove" onClick={() => onRemove(qid)} aria-label="Quitar de la cola">×</button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
