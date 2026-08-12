import { browser } from '$app/environment';
import {
	PUBLIC_FIREBASE_API_KEY,
	PUBLIC_FIREBASE_APP_ID,
	PUBLIC_FIREBASE_AUTH_DOMAIN,
	PUBLIC_FIREBASE_DATABASE_URL,
	PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
	PUBLIC_FIREBASE_PROJECT_ID,
	PUBLIC_FIREBASE_STORAGE_BUCKET
} from '$env/static/public';
import { getApp, getApps, initializeApp, type FirebaseApp } from 'firebase/app';
import { getDatabase, type Database } from 'firebase/database';
import { getStorage, type FirebaseStorage } from 'firebase/storage';

const config = {
	apiKey: PUBLIC_FIREBASE_API_KEY,
	authDomain: PUBLIC_FIREBASE_AUTH_DOMAIN,
	databaseURL: PUBLIC_FIREBASE_DATABASE_URL,
	projectId: PUBLIC_FIREBASE_PROJECT_ID,
	storageBucket: PUBLIC_FIREBASE_STORAGE_BUCKET,
	messagingSenderId: PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
	appId: PUBLIC_FIREBASE_APP_ID
};

const configNames: Record<keyof typeof config, string> = {
	apiKey: 'PUBLIC_FIREBASE_API_KEY',
	authDomain: 'PUBLIC_FIREBASE_AUTH_DOMAIN',
	databaseURL: 'PUBLIC_FIREBASE_DATABASE_URL',
	projectId: 'PUBLIC_FIREBASE_PROJECT_ID',
	storageBucket: 'PUBLIC_FIREBASE_STORAGE_BUCKET',
	messagingSenderId: 'PUBLIC_FIREBASE_MESSAGING_SENDER_ID',
	appId: 'PUBLIC_FIREBASE_APP_ID'
};

export function missingFirebaseConfigKeys() {
	return (Object.keys(config) as Array<keyof typeof config>)
		.filter((key) => typeof config[key] !== 'string' || config[key].length === 0)
		.map((key) => configNames[key]);
}

export function isFirebaseConfigured() {
	return missingFirebaseConfigKeys().length === 0;
}

function app(): FirebaseApp {
	if (!browser) throw new Error('Firebase client is only available in the browser.');
	if (!isFirebaseConfigured()) {
		throw new Error(`Firebase 환경변수가 설정되지 않았습니다: ${missingFirebaseConfigKeys().join(', ')}`);
	}
	return getApps().length > 0 ? getApp() : initializeApp(config);
}

export function firebaseDatabase(): Database {
	return getDatabase(app());
}

export function firebaseStorage(): FirebaseStorage {
	return getStorage(app());
}
