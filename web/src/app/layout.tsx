import type { Metadata } from "next";
import { Geist, Geist_Mono, Playfair_Display } from "next/font/google";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { MocksProvider } from "@/app/mocks-provider";
import { Providers } from "@/app/providers";
import { AuthProvider } from "@/components/auth/auth-provider";
import { Toaster } from "@/components/ui/sonner";

const geistSans = Geist({
  variable: "--font-geist-sans",
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
      className={`${geistSans.variable} ${geistMono.variable} ${playfair.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          storageKey="resonance-theme"
          disableTransitionOnChange
        >
          <Providers>
            <MocksProvider>
              <AuthProvider>
                {children}
                <Toaster position="top-center" />
              </AuthProvider>
            </MocksProvider>
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}
