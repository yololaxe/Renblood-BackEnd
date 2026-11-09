package fr.renblood.medievalcoins.client.economy;
public class FitLayoutCheck {
 public static void main(String[]args){int cases=0;for(int[] viewport:new int[][]{{320,240},{426,240},{640,360},{854,480},{1920,1080}}){for(int[] image:new int[][]{{176,166},{276,196},{370,260}}){double s=FitLayout.scale(viewport[0],viewport[1],image[0],image[1]);if(image[0]*s>viewport[0]-16.0+.001||(image[1]+64)*s>viewport[1]-16.0+.001)throw new AssertionError("screen exceeds viewport");for(double x:new double[]{0,17,100,275})if(Math.abs(FitLayout.logical(x*s,s)-x)>.00001)throw new AssertionError("pointer mismatch");cases++;}}System.out.println(cases+" layout cases and 60 coordinate roundtrips passed");}
}
