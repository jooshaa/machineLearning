declare module 'express' {
  export const static: (...args: any[]) => any;
  export interface Request {
    [key: string]: any;
  }
}

declare module 'multer' {
  export interface File {
    originalname: string;
    filename: string;
    [key: string]: any;
  }

  export const diskStorage: (...args: any[]) => any;
}
