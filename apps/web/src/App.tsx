import { FormEvent, useEffect, useRef, useState } from "react";
import { ApiError, addFavorite, addTrackToPlaylist, clearTokens, createPlaylist, deletePlaylist, discoveryHome, getPlaylist, getTrackDetail, listFavorites, listPlaylistTracks, listPlaylists, login, me, register, removeFavorite, removeTrackFromPlaylist, renamePlaylist, reorderPlaylistTracks, searchTracks } from "./api";
import { KbyPlayer } from "./player";
import { QueueSheet } from "./QueueSheet";
import { buildDefaultQueue, mergeQueueMeta, trackArtistsLabel, type QueueTrackMeta } from "./queue";

// FULL APP CONTENT - will be replaced with complete file via follow-up if truncated
export default function App() {
  return <div className="app-shell">Loading full App…</div>;
}
