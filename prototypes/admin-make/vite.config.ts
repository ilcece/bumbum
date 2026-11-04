import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({base:"./",plugins:[tailwindcss()],server:{host:"0.0.0.0"},build:{chunkSizeWarningLimit:1500}});
