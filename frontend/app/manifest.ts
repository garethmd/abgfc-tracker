import type { MetadataRoute } from "next";

// Lets Android "Add to Home Screen" install it as an app with the crest and the right name.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ABGFC",
    short_name: "ABGFC",
    description: "Aldershot Boys & Girls FC — team stats",
    start_url: "/",
    display: "standalone",
    background_color: "#fafafa",
    theme_color: "#fafafa",
    icons: [{ src: "/icon.png", sizes: "512x512", type: "image/png" }],
  };
}
