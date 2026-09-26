import type { Metadata } from "next";
import {
  Geist_Mono,
  Playfair_Display,
  Schibsted_Grotesk,
} from "next/font/google";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { Providers } from "@/app/providers";
import { AuthProvider } from "@/components/auth/auth-provider";
import { Toaster } from "@/components/ui/sonner";

const schibsted = Schibsted_Grotesk({
  variable: "--font-schibsted",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Display serif for the marketing hero only. The product UI stays sans.
const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Resonance — Creator Helper Studio",
  description: "AI review studio for creators.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${schibsted.variable} ${geistMono.variable} ${playfair.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {/*
         * Runs before first paint: apply the stored sidebar state so a hard
         * refresh does not render expanded and then animate closed.
         */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{if(localStorage.getItem('hc-sidebar-collapsed')==='1'){document.documentElement.dataset.sidebar='collapsed'}}catch(e){}",
          }}
        />
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          storageKey="resonance-theme"
          disableTransitionOnChange
        >
          <Providers>
            <AuthProvider>
              {children}
              <Toaster position="top-center" />
            </AuthProvider>
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}
