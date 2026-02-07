
import GoogleProvider from "next-auth/providers/google"
import { NextAuthOptions } from "next-auth"

export const authOptions: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
    }),
  ],
  callbacks: {
    async session({ session, token }) {
      // 세선에 사용자 ID 등 추가 정보 포함 가능
      return session
    },
  },
  logger: {
    error(code, metadata) {
      console.error(code, metadata)
    },
    warn(code) {
      // ignore warnings
    },
    debug(code, metadata) {
      // ignore debug messages
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
  // pages: {
  //   signIn: '/auth/signin', // 커스텀 로그인 페이지 (옵션)
  // }
}
