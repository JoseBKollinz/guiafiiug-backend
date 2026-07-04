import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyAIbc01aeV-0UXf-TJz_kDaJYCb3qAgRvY",
  authDomain: "guiafiiug-16f30.firebaseapp.com",
  projectId: "guiafiiug-16f30",
  storageBucket: "guiafiiug-16f30.firebasestorage.app",
  messagingSenderId: "831953258374",
  appId: "1:831953258374:web:f2b7d2cd5e29b3acf84e07"
};

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
export const db = getFirestore(app);