import axios from 'axios';
export const api=axios.create({baseURL:'/api',timeout:120000});
export type Dashboard={sources:number;tables:number;columns:number;pending_reviews:number;sensitive_columns:number};
export type AssetTable={id:number;name:string;schema:string;domain:string;comment:string;confidence:number;column_count:number};
export type SearchResult={column_id:number;asset:string;business_name:string;description:string;domain:string;sensitivity:string;confidence:number;retrieval_score:number;reason:string};
